"""Main module using requests library."""

import requests
import click


def fetch_data(url: str) -> dict:
    """Fetch data from a URL using requests."""
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def get_user_agent() -> str:
    """Get the default user agent from requests."""
    return requests.utils.default_user_agent()


@click.command()
@click.option("--url", default="https://httpbin.org/get", help="URL to fetch")
def main(url: str) -> None:
    """Fetch data from URL and print result."""
    click.echo(f"Fetching {url}...")
    data = fetch_data(url)
    click.echo(f"Response: {data}")


if __name__ == "__main__":
    main()