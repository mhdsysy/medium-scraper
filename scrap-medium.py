import json
import os
import sys
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from markdownify import markdownify as md
import hashlib

# Load environment variables
load_dotenv()


class MediumScraper:
    def __init__(self,tag_slug, min_claps):
        self.tag_slug, self.min_claps = tag_slug, min_claps
        self.headers = self._load_headers()
        self.graphql_url = 'https://medium.com/_/graphql'
        self.downloaded_articles = self._generate_downloaded_articles_hashset()

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
        print(f"Extracted highest resolution image URL: {highest_resolution_image}")
        return highest_resolution_image

    def _download_image(self, image_url, image_name, article_folder):
        images_directory = os.path.join(article_folder, "images")
        # Ensure base and article-specific folder exists
        if not os.path.exists(images_directory):
            os.makedirs(images_directory)

        # Construct the full path for the image
        # Assuming PNG format, adjust if necessary
        image_path = os.path.join(images_directory, f"{image_name}.png")

        # Download and save the image
        print(f"Downloading image: {image_url} to {image_path}")
        response = requests.get(image_url, stream=True, headers=self.headers)
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

    def _load_headers(self):
        """Load request headers including environment variables."""
        cookie_value = os.getenv("COOKIE")
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en",
            "Cache-Control": "max-age=0",
            # Use the cookie value from the .env file
            "Cookie": f'{cookie_value}',
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        }

    def _generate_downloaded_articles_hashset(self):
        """Generate a hashset of all downloaded articles' identifiers."""
        hashset = set()
        for root, dirs, files in os.walk("medium-articles"):
            for file in files:
                if file.endswith(".md"):
                    file_name = file.title().lower()
                    print(f"Caching file {file_name}")
                    # Use the file name or a hash of the file path as the unique identifier
                    article_id = hashlib.md5(file_name.encode()).hexdigest()
                    hashset.add(article_id)
        return hashset

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

        response = requests.post(self.graphql_url, headers=self.headers, json=payload)
        if response.status_code == 200:
            # Parse the JSON response
            json_data = response.json()
            # Extract the clap count
            clap_count = json_data[0].get("data", {}).get("postResult", {}).get("clapCount", 0)
            return clap_count
        else:
            print(f"Failed to fetch clap count: HTTP {response.status_code}")
            return None

    def _fetch_and_convert_article_section_to_markdown(self, url):
        """Fetch an article, convert it to markdown, and save locally."""
        print(f"Fetching article {url}")
        article_folder_name = url.split('/')[-1]
        article_folder_path = os.path.join("medium-articles", self.tag_slug, str(self.min_claps), article_folder_name)
        file_name = f"{article_folder_name}.md"
        file_path = os.path.join(article_folder_path, file_name)
        article_id = hashlib.md5(file_name.lower().encode()).hexdigest()
        if article_id in self.downloaded_articles:
            print(f"Article already downloaded: {url}")
            return  # Skip downloading this article
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            if self.is_json(response.text) and self._check_for_errors(response.json()):
                print(response.text)
                sys.exit(1)
            soup = BeautifulSoup(response.content, 'html.parser')

            if not os.path.exists(article_folder_path):
                os.makedirs(article_folder_path)
            article_section = soup.find('article')
            if article_section:
                self._process_article_images(article_section, article_folder_path)
                markdown_content = md(str(article_section), heading_style="ATX")

                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(markdown_content)
                print(f"Article section saved to {file_path}")
            else:
                print("Article section not found")
        else:
            print("Failed to retrieve the article")

    def _process_article_images(self, article_section, article_folder_path):
        """Process and download all images within an article section."""
        figures = article_section.find_all('figure')
        for figure in figures:
            picture = figure.find('picture')
            figcaption = figure.find('figcaption')
            if picture and figcaption:
                source = picture.find('source')
                if source and 'srcset' in source.attrs:
                    srcset = source['srcset']
                    highest_resolution_image = self._extract_highest_resolution_image(srcset)
                    image_name = figcaption.find('strong').text if figcaption.find('strong') else "image"
                    self._download_image(highest_resolution_image, image_name, article_folder_path)

    def fetch_posts(self, from_page):
        """Fetch posts from Medium and process them."""
        payload = [{
            "operationName": "WebInlineTopicFeedQuery",
            "variables": {
                "tagSlug": f"{self.tag_slug}",
                "paging": {"from": f"{from_page}", "limit": 25},
                "skipCache": True
            },
            "query": """query WebInlineTopicFeedQuery($tagSlug: String!, $paging: PagingOptions!, $skipCache: Boolean) { personalisedTagFeed(tagSlug: $tagSlug, paging: $paging, skipCache: $skipCache) { items { ... on TagFeedItem { post { id creator { username } title uniqueSlug __typename } __typename } __typename } pagingInfo { next { source limit from to __typename } __typename } __typename } }"""
        }]
        print(f"Fetching posts starting from index {from_page}...")
        response = requests.post(self.graphql_url, headers=self.headers, json=payload)
        if response.status_code == 200:
            data = response.json()

            if self.is_json(response.text) and self._check_for_errors(data):
                print(response.text)
                return False

            if data[0]['data']['personalisedTagFeed']['items']:
                for item in data[0]['data']['personalisedTagFeed']['items']:
                    post = item['post']
                    post_id = post['id']
                    username = post['creator']['username']
                    postSlug = post['uniqueSlug']
                    full_url = f"https://medium.com/@{username}/{postSlug}"
                    print(full_url)
                    clap_count = self._fetch_clap_count(post_id)
                    if clap_count < self.min_claps:
                        print(f"Skipping this article {full_url}, since the number of it's claps {clap_count} is lower than the minimum of {self.min_claps}.")
                        continue
                    self._fetch_and_convert_article_section_to_markdown(full_url)
                return True
            else:
                print(f"No more posts found. The server returned the following status code '{response.status_code}' and the following response payload '{response.text}'.")
                return False
        else:
            print(f"Failed to retrieve content: HTTP {response.status_code}")
            print("Response text:", response.text)
            return False

    def run(self):
        """Entry point to start the scraper."""
        from_page = 0
        while True:
            if not self.fetch_posts(from_page=from_page):
                break
            from_page += 25


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python script.py <tagSlug> <min_claps>")
        sys.exit(1)
    tag_slug = sys.argv[1]
    min_claps = int(sys.argv[2])
    while min_claps > 0:
        scraper = MediumScraper(tag_slug=tag_slug, min_claps=min_claps)
        min_claps -= 500
        scraper.run()
