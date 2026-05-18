FROM python:3.14-slim

# Install tzdata to ensure timezones are available
RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pyproject.toml and the source directory
COPY pyproject.toml .
COPY src/ ./src/

# Install the project and its dependencies
RUN pip install --no-cache-dir .

# Create audio directory
RUN mkdir -p audio

# Set environment variables (defaults)
ENV LATITUDE=40.7128
ENV LONGITUDE=-74.0060
ENV TIMEZONE=America/New_York
ENV CALCULATION_METHOD=NORTH_AMERICA
ENV MADHAB=SHAFI
ENV REMIND_BEFORE_MINUTES=0
ENV SERVER_PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Set the system timezone in the container
ENV TZ=America/New_York

# Use the installed script entry point
CMD ["sonos-athan"]
