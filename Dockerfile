# This is a docker file to run anki server based on ubuntu 22.04

# Use the official ubuntu 22.04 image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

COPY . /app
# Install anki's python package
RUN pip install -r requirements.txt

EXPOSE 5000

# Run flash server when the container launches
CMD ["python", "server.py"]