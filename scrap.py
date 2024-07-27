import argparse
import json
import os
import random
import sys
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from markdownify import markdownify as md
import hashlib

# Load environment variables
load_dotenv()

ARTICLES_DIRECTORY = 'medium-articles'
GRAPHQL_URL = 'https://medium.com/_/graphql'
COOKIE_VALUE = os.getenv("COOKIE")
HEADERS = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en",
            "Cache-Control": "max-age=0",
            "Cookie": f'{COOKIE_VALUE}',  # Use the cookie value from the .env file
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1"
        }

class MediumScraper:
    def __init__(self, mode='select'):
        self.downloaded_articles = self._generate_downloaded_articles_hashset()
        self.tag_slugs = self._fetch_tag_slugs()
        self.mode = mode
        self.chosen_tags = None

    @staticmethod
    def is_json(response_text):
        try:
            # Attempt to parse the text as JSON
            json.loads(response_text)
            # If parsing succeeds, return True
            return True
        except json.JSONDecodeError:
            # If an error is raised, the text is not valid JSON
            return False

    @staticmethod
    def _check_for_errors(response_data):
        # Check if there's an "errors" key in the response
        if response_data and "errors" in response_data[0]:
            return True
        else:
            return False

    @staticmethod
    def _extract_highest_resolution_image(srcset):
        """Extract the highest resolution image URL from srcset."""
        images = srcset.split(",")
        highest_resolution_image = images[-1].strip().split(" ")[0]
        # Log the extracted URL
        print(
            f"Extracted highest resolution image URL: {highest_resolution_image}")
        return highest_resolution_image

    @staticmethod
    def _generate_downloaded_articles_hashset():
        """Generate a hashset of all downloaded articles' identifiers."""
        hashset = set()
        for root, dirs, files in os.walk(ARTICLES_DIRECTORY):
            for file in files:
                if file.endswith(".md"):
                    file_name = file.title().lower().removesuffix(".md").strip()
                    print(f"Caching file {file_name}")
                    hashset.add(file_name)
        return hashset

    @staticmethod
    def _fetch_tag_slugs():
        payload = [
            {
                "operationName": "HomeMainContentHeaderQuery",
                "variables": {},
                "query": "query HomeMainContentHeaderQuery($paging: PagingOptions) {\n  viewer {\n    ...HomeFeedNavbar_viewer\n    __typename\n  } \n}\n\nfragment HomeFeedNavbar_viewer on User {\n  id\n  followedTags(paging: $paging) {\n    tags {\n      __typename\n         id\n      displayTitle\n    }\n    __typename\n  }\n  __typename\n}\n"
            }
        ]
        response = requests.post(GRAPHQL_URL, headers=HEADERS, json=payload)
        if MediumScraper.is_json(response.text) and MediumScraper._check_for_errors(response.json()):
            print(response.text)
            sys.exit(1)
        if response.status_code == 200:
            json_response = response.json()
            tags = json_response[0]['data']['viewer']['followedTags']['tags']
            return sorted([(tag['id']) for tag in tags])
        else:
            print(f"Failed to fetch data {response.status_code}")
            print(response.text)
            sys.exit(1)


    def _download_image(self, image_url, article_folder):
        images_directory = os.path.join(article_folder, "images")
        # Ensure base and article-specific folder exists
        if not os.path.exists(images_directory):
            os.makedirs(images_directory)

        hashed_image_name = hashlib.md5(image_url.encode()).hexdigest()
        # Construct the full path for the image
        image_path = os.path.join(images_directory, f"{hashed_image_name}.png")

        # Download and save the image
        print(f"Downloading image: {image_url} to {image_path}")
        response = requests.get(image_url, stream=True, headers=HEADERS)
        if response.status_code == 200:
            if self.is_json(response.text) and self._check_for_errors(response.json()):
                print(response.text)
                sys.exit(1)
            with open(image_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            print(f"Image saved as {image_path}")
            # Return the relative path to the image for Markdown linking
            return os.path.relpath(image_path, article_folder)
        else:
            print(f"Failed to download {image_url}")
            return None

    def _get_clap_range_for_clap_count(self, clap_count):
        """ Determine the clap range folder name based on clap count. """
        if clap_count == 0:
            return '0'
        range_start = (clap_count // 500) * 500
        return f"{range_start}-{range_start + 499}"
    
    # Function to fetch clap count for a given Medium post
    def _fetch_clap_count(self, post_id):
        # Define the GraphQL query and variables
        payload = [
            {
                "operationName": "ClapCountQuery",
                "variables": {
                    "postId": f"{post_id}"
                },
                "query": "query ClapCountQuery($postId: ID!) {\n  postResult(id: $postId) {\n    __typename\n    ... on Post {\n      id\n      clapCount\n      __typename\n    }\n  }\n}\n"
            }
        ]

        response = requests.post(GRAPHQL_URL, headers=HEADERS, json=payload)
        if self.is_json(response.text) and self._check_for_errors(response.json()):
            print(response.text)
            sys.exit(1)
        if response.status_code == 200:
            # Parse the JSON response
            json_data = response.json()
            # Extract the clap count
            clap_count = json_data[0].get("data", {}).get(
                "postResult", {}).get("clapCount", 0)
            return clap_count
        else:
            print(f"Failed to fetch clap count: HTTP {response.status_code}")
            return None

    def _preprocess_html_for_images(self, soup):
        figures = soup.find_all('figure')
        image_info_list = []
        for i, figure in enumerate(figures):
            picture = figure.find('picture')
            if picture:
                source = picture.find('source')
                if source and 'srcset' in source.attrs:
                    srcset = source['srcset']
                    highest_resolution_image = self._extract_highest_resolution_image(
                        srcset)
                    # Create a unique placeholder for each image
                    placeholder = f"{{{{IMAGE_PLACEHOLDER_{i}}}}}"
                    figure.replace_with(placeholder)
                    # Modified placeholder for markdownify's escaped format
                    escaped_placeholder = placeholder.replace("_", "\\_")
                    image_info_list.append(
                        (highest_resolution_image, escaped_placeholder))
        return image_info_list

    def _fetch_and_convert_article_section_to_markdown(self, url, tag_slug, clap_range):
        """Fetch an article, convert it to markdown, and save locally."""
        print(f"Fetching article {url}")
        article_folder_name = url.split('/')[-1].strip()
        article_folder_path = os.path.join(ARTICLES_DIRECTORY, tag_slug, str(clap_range), article_folder_name)
        file_name = f"{article_folder_name}.md"
        file_path = os.path.join(article_folder_path, file_name)
        if article_folder_name in self.downloaded_articles:
            print(f"Article already downloaded: {url}")
            return  # Skip downloading this article
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            if self.is_json(response.text) and self._check_for_errors(response.json()):
                print(response.text)
                sys.exit(1)
            soup = BeautifulSoup(response.content, 'html.parser')

            if not os.path.exists(article_folder_path):
                os.makedirs(article_folder_path)
            article_section = soup.find('article')
            if article_section:
                image_info_list = self._preprocess_html_for_images(article_section)
                markdown_content = md(str(article_section), heading_style="ATX")
                # Replace placeholders with actual image paths
                for image_url, placeholder in image_info_list:
                    relative_image_path = self._download_image(image_url, article_folder_path)
                    if relative_image_path:
                        markdown_content = markdown_content.replace(placeholder, f"![]({relative_image_path})", 1)

                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(markdown_content)
                print(f"Article section saved to {file_path}")
            else:
                print("Article section not found")
        else:
            print("Failed to retrieve the article")

    def fetch_posts(self, from_page, tag_slug):
        """Fetch posts from Medium and process them."""
        recommended_feed = tag_slug == "recommended"
        payload = [{
            "operationName": "WebInlineTopicFeedQuery",
            "variables": {
                "tagSlug": f"{tag_slug}",
                "paging": {"from": f"{from_page}", "limit": 25},
                "skipCache": True
            },
            "query": """query WebInlineTopicFeedQuery($tagSlug: String!, $paging: PagingOptions!, $skipCache: Boolean) { personalisedTagFeed(tagSlug: $tagSlug, paging: $paging, skipCache: $skipCache) { items { ... on TagFeedItem { post { id creator { username } title uniqueSlug __typename } __typename } __typename } pagingInfo { next { source limit from to __typename } __typename } __typename } }"""
        }]

        payload_for_recommended_feed = [{
            "operationName": "WebInlineRecommendedFeedQuery",
            "variables": {
                "forceRank": True,
                "paging": {"from": f"{from_page}", "limit": 25},
                "skipCache": True
            },
            "query": "query WebInlineRecommendedFeedQuery($paging: PagingOptions, $forceRank: Boolean) {\n  webRecommendedFeed(paging: $paging, forceRank: $forceRank) {\n    items {\n      ...InlineFeed_homeFeedItem\n      reasonString\n      __typename\n    }\n    pagingInfo {\n      next {\n        limit\n        to\n        source\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment InlineFeed_homeFeedItem on HomeFeedItem {\n  feedId\n  moduleSourceEncoding\n  reason\n  post {\n    ...InlineFeed_post\n    __typename\n    id\n  }\n  __typename\n}\n\nfragment InlineFeed_post on Post {\n  ...PostPreview_post\n  __typename\n  id\n}\n\nfragment PostPreview_post on Post {\n  id\n  creator {\n    ...PostPreview_user\n    __typename\n    id\n  }\n  collection {\n    ...CardByline_collection\n    ...ExpandablePostByline_collection\n    __typename\n    id\n  }\n  ...InteractivePostBody_postPreview\n  firstPublishedAt\n  isLocked\n  isSeries\n  latestPublishedAt\n  inResponseToCatalogResult {\n    __typename\n  }\n  pinnedAt\n  pinnedByCreatorAt\n  previewImage {\n    id\n    focusPercentX\n    focusPercentY\n    __typename\n  }\n  readingTime\n  sequence {\n    slug\n    __typename\n  }\n  title\n  uniqueSlug\n  ...CardByline_post\n  ...PostFooterActionsBar_post\n  ...InResponseToEntityPreview_post\n  ...PostScrollTracker_post\n  ...HighDensityPreview_post\n  __typename\n}\n\nfragment PostPreview_user on User {\n  __typename\n  name\n  username\n  ...CardByline_user\n  ...ExpandablePostByline_user\n  id\n}\n\nfragment CardByline_user on User {\n  __typename\n  id\n  name\n  username\n  mediumMemberAt\n  socialStats {\n    followerCount\n    __typename\n  }\n  ...useIsVerifiedBookAuthor_user\n  ...userUrl_user\n  ...UserMentionTooltip_user\n}\n\nfragment useIsVerifiedBookAuthor_user on User {\n  verifications {\n    isBookAuthor\n    __typename\n  }\n  __typename\n  id\n}\n\nfragment userUrl_user on User {\n  __typename\n  id\n  customDomainState {\n    live {\n      domain\n      __typename\n    }\n    __typename\n  }\n  hasSubdomain\n  username\n}\n\nfragment UserMentionTooltip_user on User {\n  id\n  name\n  username\n  bio\n  imageId\n  mediumMemberAt\n  membership {\n    tier\n    __typename\n    id\n  }\n  ...UserAvatar_user\n  ...UserFollowButton_user\n  ...useIsVerifiedBookAuthor_user\n  __typename\n}\n\nfragment UserAvatar_user on User {\n  __typename\n  id\n  imageId\n  mediumMemberAt\n  membership {\n    tier\n    __typename\n    id\n  }\n  name\n  username\n  ...userUrl_user\n}\n\nfragment UserFollowButton_user on User {\n  ...UserFollowButtonSignedIn_user\n  ...UserFollowButtonSignedOut_user\n  __typename\n  id\n}\n\nfragment UserFollowButtonSignedIn_user on User {\n  id\n  name\n  __typename\n}\n\nfragment UserFollowButtonSignedOut_user on User {\n  id\n  ...SusiClickable_user\n  __typename\n}\n\nfragment SusiClickable_user on User {\n  ...SusiContainer_user\n  __typename\n  id\n}\n\nfragment SusiContainer_user on User {\n  ...SignInOptions_user\n  ...SignUpOptions_user\n  __typename\n  id\n}\n\nfragment SignInOptions_user on User {\n  id\n  name\n  __typename\n}\n\nfragment SignUpOptions_user on User {\n  id\n  name\n  __typename\n}\n\nfragment ExpandablePostByline_user on User {\n  __typename\n  id\n  name\n  imageId\n  ...userUrl_user\n  ...useIsVerifiedBookAuthor_user\n}\n\nfragment CardByline_collection on Collection {\n  name\n  ...collectionUrl_collection\n  __typename\n  id\n}\n\nfragment collectionUrl_collection on Collection {\n  id\n  domain\n  slug\n  __typename\n}\n\nfragment ExpandablePostByline_collection on Collection {\n  __typename\n  id\n  name\n  domain\n  slug\n}\n\nfragment InteractivePostBody_postPreview on Post {\n  extendedPreviewContent(\n    truncationConfig: {previewParagraphsWordCountThreshold: 400, minimumWordLengthForTruncation: 150, truncateAtEndOfSentence: true, showFullImageCaptions: true, shortformPreviewParagraphsWordCountThreshold: 30, shortformMinimumWordLengthForTruncation: 30}\n  ) {\n    bodyModel {\n      ...PostBody_bodyModel\n      __typename\n    }\n    isFullContent\n    __typename\n  }\n  __typename\n  id\n}\n\nfragment PostBody_bodyModel on RichText {\n  sections {\n    name\n    startIndex\n    textLayout\n    imageLayout\n    backgroundImage {\n      id\n      originalHeight\n      originalWidth\n      __typename\n    }\n    videoLayout\n    backgroundVideo {\n      videoId\n      originalHeight\n      originalWidth\n      previewImageId\n      __typename\n    }\n    __typename\n  }\n  paragraphs {\n    id\n    ...PostBodySection_paragraph\n    __typename\n  }\n  ...normalizedBodyModel_richText\n  __typename\n}\n\nfragment PostBodySection_paragraph on Paragraph {\n  name\n  ...PostBodyParagraph_paragraph\n  __typename\n  id\n}\n\nfragment PostBodyParagraph_paragraph on Paragraph {\n  name\n  type\n  ...ImageParagraph_paragraph\n  ...TextParagraph_paragraph\n  ...IframeParagraph_paragraph\n  ...MixtapeParagraph_paragraph\n  ...CodeBlockParagraph_paragraph\n  __typename\n  id\n}\n\nfragment ImageParagraph_paragraph on Paragraph {\n  href\n  layout\n  metadata {\n    id\n    originalHeight\n    originalWidth\n    focusPercentX\n    focusPercentY\n    alt\n    __typename\n  }\n  ...Markups_paragraph\n  ...ParagraphRefsMapContext_paragraph\n  ...PostAnnotationsMarker_paragraph\n  __typename\n  id\n}\n\nfragment Markups_paragraph on Paragraph {\n  name\n  text\n  hasDropCap\n  dropCapImage {\n    ...MarkupNode_data_dropCapImage\n    __typename\n    id\n  }\n  markups {\n    ...Markups_markup\n    __typename\n  }\n  __typename\n  id\n}\n\nfragment MarkupNode_data_dropCapImage on ImageMetadata {\n  ...DropCap_image\n  __typename\n  id\n}\n\nfragment DropCap_image on ImageMetadata {\n  id\n  originalHeight\n  originalWidth\n  __typename\n}\n\nfragment Markups_markup on Markup {\n  type\n  start\n  end\n  href\n  anchorType\n  userId\n  linkMetadata {\n    httpStatus\n    __typename\n  }\n  __typename\n}\n\nfragment ParagraphRefsMapContext_paragraph on Paragraph {\n  id\n  name\n  text\n  __typename\n}\n\nfragment PostAnnotationsMarker_paragraph on Paragraph {\n  ...PostViewNoteCard_paragraph\n  __typename\n  id\n}\n\nfragment PostViewNoteCard_paragraph on Paragraph {\n  name\n  __typename\n  id\n}\n\nfragment TextParagraph_paragraph on Paragraph {\n  type\n  hasDropCap\n  codeBlockMetadata {\n    mode\n    lang\n    __typename\n  }\n  ...Markups_paragraph\n  ...ParagraphRefsMapContext_paragraph\n  __typename\n  id\n}\n\nfragment IframeParagraph_paragraph on Paragraph {\n  type\n  iframe {\n    mediaResource {\n      id\n      iframeSrc\n      iframeHeight\n      iframeWidth\n      title\n      __typename\n    }\n    __typename\n  }\n  layout\n  ...Markups_paragraph\n  __typename\n  id\n}\n\nfragment MixtapeParagraph_paragraph on Paragraph {\n  type\n  mixtapeMetadata {\n    href\n    mediaResource {\n      mediumCatalog {\n        id\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  ...GenericMixtapeParagraph_paragraph\n  __typename\n  id\n}\n\nfragment GenericMixtapeParagraph_paragraph on Paragraph {\n  text\n  mixtapeMetadata {\n    href\n    thumbnailImageId\n    __typename\n  }\n  markups {\n    start\n    end\n    type\n    href\n    __typename\n  }\n  __typename\n  id\n}\n\nfragment CodeBlockParagraph_paragraph on Paragraph {\n  codeBlockMetadata {\n    lang\n    mode\n    __typename\n  }\n  __typename\n  id\n}\n\nfragment normalizedBodyModel_richText on RichText {\n  paragraphs {\n    ...normalizedBodyModel_richText_paragraphs\n    __typename\n  }\n  sections {\n    startIndex\n    ...getSectionEndIndex_section\n    __typename\n  }\n  ...getParagraphStyles_richText\n  ...getParagraphSpaces_richText\n  __typename\n}\n\nfragment normalizedBodyModel_richText_paragraphs on Paragraph {\n  markups {\n    ...normalizedBodyModel_richText_paragraphs_markups\n    __typename\n  }\n  codeBlockMetadata {\n    lang\n    mode\n    __typename\n  }\n  ...getParagraphHighlights_paragraph\n  ...getParagraphPrivateNotes_paragraph\n  __typename\n  id\n}\n\nfragment normalizedBodyModel_richText_paragraphs_markups on Markup {\n  type\n  __typename\n}\n\nfragment getParagraphHighlights_paragraph on Paragraph {\n  name\n  __typename\n  id\n}\n\nfragment getParagraphPrivateNotes_paragraph on Paragraph {\n  name\n  __typename\n  id\n}\n\nfragment getSectionEndIndex_section on Section {\n  startIndex\n  __typename\n}\n\nfragment getParagraphStyles_richText on RichText {\n  paragraphs {\n    text\n    type\n    __typename\n  }\n  sections {\n    ...getSectionEndIndex_section\n    __typename\n  }\n  __typename\n}\n\nfragment getParagraphSpaces_richText on RichText {\n  paragraphs {\n    layout\n    metadata {\n      originalHeight\n      originalWidth\n      id\n      __typename\n    }\n    type\n    ...paragraphExtendsImageGrid_paragraph\n    __typename\n  }\n  ...getSeriesParagraphTopSpacings_richText\n  ...getPostParagraphTopSpacings_richText\n  __typename\n}\n\nfragment paragraphExtendsImageGrid_paragraph on Paragraph {\n  layout\n  type\n  __typename\n  id\n}\n\nfragment getSeriesParagraphTopSpacings_richText on RichText {\n  paragraphs {\n    id\n    __typename\n  }\n  sections {\n    ...getSectionEndIndex_section\n    __typename\n  }\n  __typename\n}\n\nfragment getPostParagraphTopSpacings_richText on RichText {\n  paragraphs {\n    type\n    layout\n    text\n    codeBlockMetadata {\n      lang\n      mode\n      __typename\n    }\n    __typename\n  }\n  sections {\n    ...getSectionEndIndex_section\n    __typename\n  }\n  __typename\n}\n\nfragment CardByline_post on Post {\n  ...DraftStatus_post\n  ...Star_post\n  ...shouldShowPublishedInStatus_post\n  __typename\n  id\n}\n\nfragment DraftStatus_post on Post {\n  id\n  pendingCollection {\n    id\n    creator {\n      id\n      __typename\n    }\n    ...BoldCollectionName_collection\n    __typename\n  }\n  statusForCollection\n  creator {\n    id\n    __typename\n  }\n  isPublished\n  __typename\n}\n\nfragment BoldCollectionName_collection on Collection {\n  id\n  name\n  __typename\n}\n\nfragment Star_post on Post {\n  id\n  creator {\n    id\n    __typename\n  }\n  __typename\n}\n\nfragment shouldShowPublishedInStatus_post on Post {\n  statusForCollection\n  isPublished\n  __typename\n  id\n}\n\nfragment PostFooterActionsBar_post on Post {\n  id\n  visibility\n  allowResponses\n  postResponses {\n    count\n    __typename\n  }\n  isLimitedState\n  creator {\n    id\n    __typename\n  }\n  collection {\n    id\n    __typename\n  }\n  ...MultiVote_post\n  ...PostSharePopover_post\n  ...OverflowMenuButtonWithNegativeSignal_post\n  ...BookmarkButton_post\n  __typename\n}\n\nfragment MultiVote_post on Post {\n  id\n  creator {\n    id\n    ...SusiClickable_user\n    __typename\n  }\n  isPublished\n  ...SusiClickable_post\n  collection {\n    id\n    slug\n    __typename\n  }\n  isLimitedState\n  ...MultiVoteCount_post\n  __typename\n}\n\nfragment SusiClickable_post on Post {\n  id\n  mediumUrl\n  ...SusiContainer_post\n  __typename\n}\n\nfragment SusiContainer_post on Post {\n  id\n  __typename\n}\n\nfragment MultiVoteCount_post on Post {\n  id\n  __typename\n}\n\nfragment PostSharePopover_post on Post {\n  id\n  mediumUrl\n  title\n  isPublished\n  isLocked\n  ...usePostUrl_post\n  ...FriendLink_post\n  __typename\n}\n\nfragment usePostUrl_post on Post {\n  id\n  creator {\n    ...userUrl_user\n    __typename\n    id\n  }\n  collection {\n    id\n    domain\n    slug\n    __typename\n  }\n  isSeries\n  mediumUrl\n  sequence {\n    slug\n    __typename\n  }\n  uniqueSlug\n  __typename\n}\n\nfragment FriendLink_post on Post {\n  id\n  ...SusiClickable_post\n  ...useCopyFriendLink_post\n  ...UpsellClickable_post\n  __typename\n}\n\nfragment useCopyFriendLink_post on Post {\n  ...usePostUrl_post\n  __typename\n  id\n}\n\nfragment UpsellClickable_post on Post {\n  id\n  collection {\n    id\n    __typename\n  }\n  sequence {\n    sequenceId\n    __typename\n  }\n  creator {\n    id\n    __typename\n  }\n  __typename\n}\n\nfragment OverflowMenuButtonWithNegativeSignal_post on Post {\n  id\n  visibility\n  ...OverflowMenuWithNegativeSignal_post\n  __typename\n}\n\nfragment OverflowMenuWithNegativeSignal_post on Post {\n  id\n  creator {\n    id\n    __typename\n  }\n  collection {\n    id\n    __typename\n  }\n  ...OverflowMenuItemUndoClaps_post\n  ...AddToCatalogBase_post\n  __typename\n}\n\nfragment OverflowMenuItemUndoClaps_post on Post {\n  id\n  clapCount\n  ...ClapMutation_post\n  __typename\n}\n\nfragment ClapMutation_post on Post {\n  __typename\n  id\n  clapCount\n  ...MultiVoteCount_post\n}\n\nfragment AddToCatalogBase_post on Post {\n  id\n  isPublished\n  ...SusiClickable_post\n  __typename\n}\n\nfragment BookmarkButton_post on Post {\n  visibility\n  ...SusiClickable_post\n  ...AddToCatalogBookmarkButton_post\n  __typename\n  id\n}\n\nfragment AddToCatalogBookmarkButton_post on Post {\n  ...AddToCatalogBase_post\n  __typename\n  id\n}\n\nfragment InResponseToEntityPreview_post on Post {\n  id\n  inResponseToEntityType\n  __typename\n}\n\nfragment PostScrollTracker_post on Post {\n  id\n  collection {\n    id\n    __typename\n  }\n  sequence {\n    sequenceId\n    __typename\n  }\n  __typename\n}\n\nfragment HighDensityPreview_post on Post {\n  id\n  title\n  previewImage {\n    id\n    focusPercentX\n    focusPercentY\n    __typename\n  }\n  extendedPreviewContent(\n    truncationConfig: {previewParagraphsWordCountThreshold: 400, minimumWordLengthForTruncation: 150, truncateAtEndOfSentence: true, showFullImageCaptions: true, shortformPreviewParagraphsWordCountThreshold: 30, shortformMinimumWordLengthForTruncation: 30}\n  ) {\n    subtitle\n    __typename\n  }\n  ...HighDensityFooter_post\n  __typename\n}\n\nfragment HighDensityFooter_post on Post {\n  id\n  readingTime\n  tags {\n    ...TopicPill_tag\n    __typename\n  }\n  ...BookmarkButton_post\n  ...ExpandablePostCardOverflowButton_post\n  ...OverflowMenuButtonWithNegativeSignal_post\n  __typename\n}\n\nfragment TopicPill_tag on Tag {\n  __typename\n  id\n  displayTitle\n  normalizedTagSlug\n}\n\nfragment ExpandablePostCardOverflowButton_post on Post {\n  creator {\n    id\n    __typename\n  }\n  ...ExpandablePostCardReaderButton_post\n  __typename\n  id\n}\n\nfragment ExpandablePostCardReaderButton_post on Post {\n  id\n  collection {\n    id\n    __typename\n  }\n  creator {\n    id\n    __typename\n  }\n  clapCount\n  ...ClapMutation_post\n  __typename\n}\n"
        }]

        print(f"Fetching posts starting from index {from_page}...")
        response = requests.post(GRAPHQL_URL, headers=HEADERS, json=payload if not recommended_feed else payload_for_recommended_feed)
        if response.status_code == 200:
            data = response.json()

            if self.is_json(response.text) and self._check_for_errors(data):
                print(response.text)
                return False

            if data[0]['data']['personalisedTagFeed' if not recommended_feed else 'webRecommendedFeed']['items']:
                for item in data[0]['data']['personalisedTagFeed' if not recommended_feed else 'webRecommendedFeed']['items']:
                    post = item['post']
                    post_id = post['id']
                    username = post['creator']['username']
                    postSlug = post['uniqueSlug']
                    full_url = f"https://medium.com/@{username}/{postSlug}"
                    print(full_url)
                    clap_count = self._fetch_clap_count(post_id)
                    clap_range = self._get_clap_range_for_clap_count(clap_count)
                    self._fetch_and_convert_article_section_to_markdown(full_url, tag_slug, clap_range=clap_range)
                    time.sleep(random.uniform(1, 5))
                return True
            else:
                print(
                    f"No more posts found. The server returned the following status code '{response.status_code}' and the following response payload '{response.text}'.")
                return False
        else:
            print(f"Failed to retrieve content: HTTP {response.status_code}")
            print("Response text:", response.text)
            return False

    def scrap(self):
        """Entry point to start the scraper based on mode."""
        if self.mode == 'select' and self.chosen_tags:
            for tag_slug in self.chosen_tags:
                self._scrap_tag(tag_slug)
        elif self.mode == 'all':
            for tag_slug in self.tag_slugs:
                self._scrap_tag(tag_slug)

    def _scrap_tag(self, tag_slug):
        """Helper method to scrape articles for a single tag slug."""
        print(f"Fetching articles for the tag slug '{tag_slug}'.")
        from_page = 0
        while True:
            if not self.fetch_posts(from_page=from_page, tag_slug=tag_slug):
                break
            from_page += 25
        time.sleep(1000)


def main():
    parser = argparse.ArgumentParser(description='Medium Scraper Options')
    parser.add_argument('--mode', type=str, choices=['all', 'select'], default='select', help='Mode to scrape: all tag slugs or select specific ones')
    args = parser.parse_args()

    scraper = MediumScraper()

    if args.mode == 'select':
        print("Available tag slugs:")
        for idx, tag in enumerate(scraper.tag_slugs):
            print(f"{idx + 1}. {tag}")

        selected_indices = input("Enter the numbers of the tag slugs you want to scrape, separated by commas (e.g., 1,4,5): ")
        chosen_tags = [scraper.tag_slugs[int(idx) - 1] for idx in selected_indices.split(',') if idx.strip().isdigit() and int(idx) <= len(scraper.tag_slugs)]

        scraper.chosen_tags = chosen_tags
    else:
        scraper.mode = 'all'

    scraper.scrap()

if __name__ == "__main__":
    main()
