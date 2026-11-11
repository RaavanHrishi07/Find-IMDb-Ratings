
import os
import re
import json
import time
import requests
import pandas as pd

from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ==========================================
# IMDb CONFIGURATION
# ==========================================

BASE_URL = "https://www.imdb.com"
SEARCH_URL = "https://www.imdb.com/find/"

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov",
    ".wmv", ".flv", ".webm", ".m4v",
    ".mpeg", ".mpg", ".3gp"
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9"
}

session = requests.Session()
session.headers.update(HEADERS)


# ==========================================
# CLEAN MOVIE FILENAMES
# ==========================================

def clean_movie_name(filename):

    name = os.path.splitext(filename)[0]

    name = re.sub(
        r"\b(1080p|720p|2160p|480p|4k|bluray|"
        r"brrip|webrip|web-dl|hdrip|dvdrip)\b",
        "",
        name,
        flags=re.IGNORECASE
    )

    name = re.sub(r"[._]+", " ", name)
    name = re.sub(r"\s+", " ", name)

    return name.strip()


# ==========================================
# GET MOVIE FILES
# ==========================================

def get_movie_files(folder_path):

    movie_files = []

    for filename in os.listdir(folder_path):

        full_path = os.path.join(folder_path, filename)

        extension = os.path.splitext(filename)[1].lower()

        if (
            os.path.isfile(full_path)
            and extension in VIDEO_EXTENSIONS
        ):
            movie_files.append(filename)

    return movie_files


# ==========================================
# SEARCH MOVIE ON IMDb
# ==========================================

def search_imdb(movie_name):

    try:

        response = session.get(
            SEARCH_URL,
            params={
                "q": movie_name,
                "s": "tt"
            },
            timeout=20
        )

        print("\n--- IMDb Diagnostic ---")
        print("Movie:", movie_name)
        print("HTTP Status:", response.status_code)
        print("Response Length:", len(response.text))
        print("Response Preview:", response.text[:300])
        print("-----------------------")

        # Detect blocked or restricted requests
        if response.status_code in (202, 403, 429):
            return {
                "status": "Request Blocked",
                "title": "",
                "url": "",
                "rating": "Not Available"
            }

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # IMDb search result selectors
        results = soup.select(
            "li.ipc-metadata-list-summary-item"
        )

        if not results:
            results = soup.select(
                "div.ipc-metadata-list-summary-item"
            )

        if not results:
            results = soup.select(
                "div.lister-item-content"
            )

        for result in results:

            link = (
                result.select_one("a.ipc-title-link-wrapper")
                or result.select_one("h3 a")
            )

            if not link:
                continue

            imdb_url = urljoin(
                BASE_URL,
                link.get("href", "")
            )

            if "/title/tt" not in imdb_url:
                continue

            title = link.get_text(" ", strip=True)

            rating_element = (
                result.select_one("span.ipc-rating-star--rating")
                or result.select_one(
                    "div.inline-block.ratings-imdb-rating"
                )
            )

            if rating_element:

                rating = (
                    rating_element.get("data-value")
                    or rating_element.get_text(strip=True)
                )

            else:
                rating = "Not Available"

            return {
                "status": "Found",
                "title": title,
                "url": imdb_url.split("?")[0],
                "rating": rating
            }

        return {
            "status": "No Results",
            "title": "",
            "url": "",
            "rating": "Not Available"
        }

    except requests.Timeout:

        print("Request timed out.")

        return {
            "status": "Network Error",
            "title": "",
            "url": "",
            "rating": "Not Available"
        }

    except requests.RequestException as error:

        print("Request error:", error)

        return {
            "status": "Network Error",
            "title": "",
            "url": "",
            "rating": "Not Available"
        }

    except Exception as error:

        print("Unexpected search error:", error)

        return {
            "status": "Processing Error",
            "title": "",
            "url": "",
            "rating": "Not Available"
        }


# ==========================================
# GET MOVIE GENRE
# ==========================================

def get_movie_genre(movie_url):

    try:

        response = session.get(
            movie_url,
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        scripts = soup.find_all(
            "script",
            type="application/ld+json"
        )

        for script in scripts:

            try:

                data = json.loads(
                    script.string or script.get_text()
                )

                if isinstance(data, list):

                    data = next(
                        (
                            item for item in data
                            if item.get("@type") in (
                                "Movie",
                                "TVSeries"
                            )
                        ),
                        {}
                    )

                if not isinstance(data, dict):
                    continue

                genre = data.get("genre", [])

                if isinstance(genre, str):
                    return genre

                if isinstance(genre, list):
                    return ", ".join(genre)

            except (json.JSONDecodeError, AttributeError):
                continue

        return "Not Available"

    except requests.RequestException as error:

        print("Genre request error:", error)

        return "Not Available"


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():

    print("\n" + "=" * 50)
    print("             FIND IMDb RATINGS")
    print("=" * 50)

    folder_path = input(
        "\nEnter the folder path containing your movies: "
    ).strip().strip('"')

    if not os.path.isdir(folder_path):

        print("\nError: Invalid folder path.")
        return

    movie_files = get_movie_files(folder_path)

    if not movie_files:

        print("\nNo supported video files found.")
        return

    print(f"\nTotal movie files found: {len(movie_files)}")
    print("\nStarting IMDb search...\n")

    results = []

    found_count = 0
    blocked_count = 0
    error_count = 0

    for index, filename in enumerate(
        movie_files,
        start=1
    ):

        movie_name = clean_movie_name(filename)

        print(
            f"\n[{index}/{len(movie_files)}] "
            f"Searching: {movie_name}"
        )

        movie_data = search_imdb(movie_name)

        status = movie_data["status"]

        if status == "Found":

            title = movie_data["title"]
            rating = movie_data["rating"]
            movie_url = movie_data["url"]

            genre = get_movie_genre(movie_url)

            found_count += 1

            print("Result:", title)
            print("Rating:", rating)
            print("Genre:", genre)

            results.append({
                "File Name": filename,
                "Film Name": title,
                "Rating": rating,
                "Genre": genre,
                "IMDb URL": movie_url,
                "Status": "Found"
            })

        else:

            if status == "Request Blocked":
                blocked_count += 1

            elif status in (
                "Network Error",
                "Processing Error"
            ):
                error_count += 1

            print("Search status:", status)

            results.append({
                "File Name": filename,
                "Film Name": movie_name,
                "Rating": "Not Available",
                "Genre": "Not Available",
                "IMDb URL": "Not Available",
                "Status": status
            })

        # Be considerate with request frequency
        time.sleep(2)

    # ======================================
    # EXPORT RESULTS TO CSV
    # ======================================

    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "film_ratings.csv"
    )

    df = pd.DataFrame(results)

    df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    # ======================================
    # FINAL SUMMARY
    # ======================================

    print("\n" + "=" * 50)
    print("             SEARCH COMPLETED")
    print("=" * 50)

    print("Total movies:", len(movie_files))
    print("Found:", found_count)
    print("Blocked requests:", blocked_count)
    print("Other errors:", error_count)
    print(
        "Not found:",
        len(movie_files) - found_count - blocked_count - error_count
    )

    print("\nCSV saved successfully:")
    print(output_path)

    print("\nThank you for using Find IMDb Ratings!")


# ==========================================
# PROGRAM ENTRY POINT
# ==========================================

if __name__ == "__main__":
    main()
