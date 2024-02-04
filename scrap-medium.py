import requests
import json
import markdownify 
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv

# Load the environment variables from the .env file
load_dotenv()

# Access the COOKIE value from environment variables
cookie_value = os.getenv("COOKIE")

# Your existing headers dictionary, now including the cookie
headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en",
    "Cache-Control": "max-age=0",
    "Cookie": cookie_value,  # Use the cookie value from the .env file
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}

# GraphQL endpoint
graphql_url = 'https://medium.com/_/graphql'

# GraphQL query payload
payload = [
    {
        "operationName": "WebInlineTopicFeedQuery",
        "variables": {
            "tagSlug": "distributed-systems",
            "paging": {
                    "from": "{from}",
                    "limit": 25
            },
            "skipCache": True
        },
        "query": """
        query WebInlineTopicFeedQuery($tagSlug: String!, $paging: PagingOptions!, $skipCache: Boolean) {
            personalisedTagFeed(tagSlug: $tagSlug, paging: $paging, skipCache: $skipCache) {
                items {
                    ... on TagFeedItem {
                        post {
                            id
                            creator {
                                username
                            }
                            title
                            uniqueSlug
                            __typename
                        }
                        __typename
                    }
                    __typename
                }
                pagingInfo {
                    next {
                        source
                        limit
                        from
                        to
                        __typename
                    }
                    __typename
                }
                __typename
            }
        }
        """
    }
]

def download_image(image_url, image_name, article_folder):
    images_directory = os.path.join(article_folder, "images")
    # Ensure base and article-specific folder exists
    if not os.path.exists(images_directory):
        os.makedirs(images_directory)

    # Construct the full path for the image
    image_path = os.path.join(images_directory, f"{image_name}.png")  # Assuming PNG format, adjust if necessary

    # Download and save the image
    print(f"Downloading image: {image_url} to {image_path}")
    response = requests.get(image_url, stream=True, headers=headers)
    if response.status_code == 200:
        with open(image_path, 'wb') as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
        print(f"Image saved as {image_path}")
        # Return the relative path to the image for Markdown linking
        return os.path.relpath(image_path, article_folder)
    else:
        print(f"Failed to download {image_url}")
        return None
        
def extract_highest_resolution_image(srcset):
    # Splitting the srcset into a list of URLs and sizes
    images = srcset.split(",")
    highest_resolution_image = images[-1].strip().split(" ")[0]  # Taking the last image URL
    print(f"Extracted highest resolution image URL: {highest_resolution_image}")  # Log the extracted URL
    return highest_resolution_image

    
def fetch_and_convert_article_section_to_markdown(url):
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        html_content = response.content
        soup = BeautifulSoup(html_content, 'html.parser')

        article_folder_name = url.split('/')[-1]
        article_folder_path = os.path.join("medium-articles", article_folder_name)

        if not os.path.exists(article_folder_path):
            os.makedirs(article_folder_path)

        article_section = soup.find('article')
        if article_section:
            figures = article_section.find_all('figure')
            image_links = {}
            for figure in figures:
                picture = figure.find('picture')
                figcaption = figure.find('figcaption')
                if picture and figcaption:
                    source = picture.find('source')
                    if source and 'srcset' in source.attrs:
                        srcset = source['srcset']
                        highest_resolution_image = extract_highest_resolution_image(srcset)
                        image_name = figcaption.find('strong').text if figcaption.find('strong') is not None else "image"
                        image_path = download_image(highest_resolution_image, image_name, article_folder_path)
                        if image_path:
                            # Store the image path with its name for later referencing
                            image_links[image_name] = image_path

            markdown_content = markdownify.markdownify(str(article_section), heading_style="ATX")

            # Insert image links into the Markdown content
            for image_name, image_path in image_links.items():
                markdown_content = markdown_content.replace(image_name, f"![{image_name}]({image_path})")

            file_name = os.path.join(article_folder_path, f"{article_folder_name}.md")
            with open(file_name, 'w', encoding='utf-8') as file:
                file.write(markdown_content)
            
            print(f"Article section saved to {file_name}")
        else:
            print("Article section not found")
    else:
        print("Failed to retrieve the article")


def fetch_posts(url, headers, payload, from_page):
    # Update the 'from' field in the payload
    current_payload = json.loads(json.dumps(payload).replace("{from}", str(from_page)))
    print(f"Fetching posts starting from index {from_page}...")

    # Send a POST request with the JSON payload
    response = requests.post(url, headers=headers, json=current_payload)

    if response.status_code == 200:
        data = response.json()
        
        # Check for errors in the response body
        if "errors" in response.text:
            print("GraphQL errors found:", data[0]["errors"])
            return False

        # Process and print URLs of fetched posts
        if data[0]['data']['personalisedTagFeed']['items']:
            for item in data[0]['data']['personalisedTagFeed']['items']:
                post = item['post']
                username = post['creator']['username']
                postSlug = post['uniqueSlug']
                full_url = f"https://medium.com/@{username}/{postSlug}"
                print(full_url)
                fetch_and_convert_article_section_to_markdown(full_url)
            return True
        else:
            print("No more posts found.")
            return False
    else:
        print(f"Failed to retrieve content: HTTP {response.status_code}")
        print("Response text:", response.text)
        return False

def main():
    from_page = 0
    while True:
        if not fetch_posts(graphql_url, headers, payload, from_page=from_page):
            break
        from_page += 25

if __name__ == "__main__":
    main()
