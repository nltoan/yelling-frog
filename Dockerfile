FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install additional dependencies
RUN pip install --no-cache-dir \
    playwright \
    aiohttp \
    aiosqlite \
    beautifulsoup4 \
    lxml \
    click \
    rich \
    pydantic

# Install Brave browser
RUN apt-get update && apt-get install -y curl apt-transport-https \
    && curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/brave-browser-archive-keyring.gpg] https://brave-browser-apt-release.s3.brave.com/ stable main" | tee /etc/apt/sources.list.d/brave-browser-release.list \
    && apt-get update \
    && apt-get install -y brave-browser \
    && rm -rf /var/lib/apt/lists/*

CMD ["bash"]
