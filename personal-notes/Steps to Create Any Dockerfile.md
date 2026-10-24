<!-- markdownlint-disable-file -->
# Steps to Create Any Dockerfile

### Step1: Choose the Base Image
Define the environment

> FROM python:3.12-slim

### Step2: Install System Tools / Pre-requisites

> RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev

### Step3: Define the Working Directory

> WORKDIR /app
