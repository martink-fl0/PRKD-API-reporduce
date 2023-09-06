# Use the official Python image as the base image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy the application code into the container
COPY . /app

# Install application dependencies
RUN pip install -r requirements.txt

# Expose the port the application will run on
EXPOSE 5000

# Define the command to start the application
# gunicorn -w 4 -b 0.0.0.0:5000 app:app
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
