# Medium Scraper

## Overview
This project is a Python-based scraper for Medium articles. It fetches posts based on a specified tag slug, downloads associated images, converts the article sections into Markdown format, and saves them locally. This tool is particularly useful for researchers, content creators, and anyone interested in archiving or analyzing articles from Medium.

## Features
- Fetch articles from Medium by tag slug.
- Download images found within the articles.
- Convert article sections to Markdown format.
- Save articles and images in a structured local directory.

## Prerequisites
Before you begin, ensure you have met the following requirements:
- Python 3.6+
- `requests`, `bs4`, `markdownify`, and `python-dotenv` libraries installed.
- A `.env` file with your Medium cookie for authenticated requests.

## Installation
Clone this repository to your local machine:
```
git clone https://github.com/yourgithubusername/medium-scraper.git
cd medium-scraper
```

Install the required Python packages:
```
pip install -r requirements.txt
```

## Usage
To use the Medium Scraper, run the following command from the root of your project directory:
```
python medium_scraper.py <tagSlug>
```
Replace `<tagSlug>` with the actual slug of the tag you're interested in.

For example:
```
python medium_scraper.py technology
```

## Configuration
- Ensure your `.env` file is set up correctly in the root directory with the following content:
```
COOKIE=your_cookie_here
```
Replace `your_cookie_here` with your actual Medium cookie value.

## Contributing
Contributions to this project are welcome. To contribute:
1. Fork the repository.
2. Create a new branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a pull request.

## License
Distributed under the MIT License. See `LICENSE` for more information.