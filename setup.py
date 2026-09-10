from setuptools import setup, find_packages

setup(
    name="stock-extractor",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "youtube-transcript-api>=0.6.0",
        "rich>=12.0.0",
        "typer>=0.9.0",
        "requests>=2.25.0",
        "deep-translator>=1.11.0"
    ],
    entry_points={
        "console_scripts": [
            "stock-yt=stock_extractor.cli:main",
        ],
    },
)
