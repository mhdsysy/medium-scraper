# Medium Scraper

This project is a Medium article scraper that fetches articles based on specified tags, converts them to Markdown, and saves them locally. It uses environment variables for sensitive data, employs GraphQL for fetching data, and handles image downloads.

## Features

- Fetch articles from Medium based on specified tags.
- Convert fetched articles to Markdown.
- Download and include images in the articles.
- Save articles locally in a structured directory format.
- Handle errors and invalid JSON responses gracefully.

## Prerequisites

- Python 3.6 or higher
- Medium account cookie for authentication
- `.env` file with the following environment variable:
  - `COOKIE`

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/yourusername/medium-scraper.git
    cd medium-scraper
    ```

2. Create a virtual environment and activate it:
    ```bash
    python -m venv venv
    source venv/bin/activate # On Windows use `venv\Scripts\activate`
    ```

3. Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

4. Create a `.env` file in the root directory of the project and add your Medium cookie:
    ```bash
    echo "COOKIE=your_medium_cookie_here" > .env
    ```

## Usage

The script can operate in two modes: `all` and `select`.

- `all`: Scrape articles for all followed tags.
- `select`: Select specific tags to scrape articles for.

### Command Line Options

- `--mode`: Mode to scrape (`all` or `select`). Default is `select`.

### Run the Scraper

```bash
python medium_scraper.py --mode select
```

In `select` mode, you will be prompted to choose tags from the available list.

## Directory Structure

Articles are saved in the `medium-articles` directory, organized by tag and clap count ranges.

```
medium-articles/
├── tag_slug_1/
│   ├── 0-499/
│   │   └── article-title.md
│   ├── 500-999/
│   │   └── another-article-title.md
│   └── images/
│       └── hashed_image_name.png
├── tag_slug_2/
│   └── ...
└── ...
```

## Script Explanation

### Key Classes and Functions

- **`MediumScraper`**: Main class for scraping Medium articles.
  - **`__init__`**: Initializes the scraper, loads downloaded articles and tag slugs.
  - **`is_json`**: Checks if a response is JSON.
  - **`_check_for_errors`**: Checks for errors in a JSON response.
  - **`_extract_highest_resolution_image`**: Extracts the highest resolution image URL from `srcset`.
  - **`_generate_downloaded_articles_hashset`**: Generates a hash set of downloaded articles.
  - **`_fetch_tag_slugs`**: Fetches tag slugs from Medium.
  - **`_download_image`**: Downloads an image and saves it locally.
  - **`_get_clap_range_for_clap_count`**: Determines the clap range based on clap count.
  - **`_fetch_clap_count`**: Fetches the clap count for a given post.
  - **`_preprocess_html_for_images`**: Preprocesses HTML to handle images.
  - **`_fetch_and_convert_article_section_to_markdown`**: Fetches an article and converts it to Markdown.
  - **`fetch_posts`**: Fetches posts from Medium and processes them.
  - **`scrap`**: Entry point to start the scraper.
  - **`_scrap_tag`**: Helper method to scrape articles for a single tag slug.

- **`main`**: Parses command line arguments and initializes the scraper.

