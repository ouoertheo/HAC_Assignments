# Dockerfile.go

FROM golang:1.19-alpine

# Set the working directory inside the container
WORKDIR /app/api

# Copy the built Go binary from the first stage
COPY  HACApi /app/api/HACApi
COPY .env /app/api/.env

# Expose any necessary ports
EXPOSE 3000

# Define the command to run when the container starts
CMD ["sudo /app/api/HACApi"]
