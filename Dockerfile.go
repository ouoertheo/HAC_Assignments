# Dockerfile.go

# Stage 1: Build the Go application
FROM golang:1.19 as go-builder

# Set the working directory inside the container
WORKDIR /go/app

# Install git to clone the repository
RUN apt install git

# Clone the Go application source code into the container
ARG REPO_URL=https://github.com/Threqt1/HACApi.git
RUN git clone $REPO_URL .
COPY .env .env

# Build the Go application
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /go/bin/go-app

# Stage 2: Create the final image
FROM alpine:latest

# Copy the built Go binary from the first stage
COPY --from=go-builder /go/bin/go-app /app/api/go-app
COPY --from=go-builder /go/app/.env /app/api/.env

# Set the working directory inside the container
WORKDIR /app/api

# Expose any necessary ports
EXPOSE 3000

# Define the command to run when the container starts
CMD ["/app/api/go-app"]
