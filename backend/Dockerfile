# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
# We need gcc and other build tools for TA-Lib
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    wget \
    tar \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib
# TA-Lib needs to be compiled from source for the python wrapper to work.
# The bundled config.guess/config.sub predate aarch64 and misdetect the
# build type on ARM64 hosts (this VM is aarch64) -- refresh them from
# upstream before configuring.
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xvzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && wget -O config.guess 'https://git.savannah.gnu.org/cgit/config.git/plain/config.guess' \
    && wget -O config.sub 'https://git.savannah.gnu.org/cgit/config.git/plain/config.sub' \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib \
    && rm ta-lib-0.4.0-src.tar.gz

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project into a subdirectory to preserve package imports
COPY . ./backend

# Set PYTHONPATH to include the /app directory
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000"]
