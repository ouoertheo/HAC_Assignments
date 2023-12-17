# Dockerfile.go

FROM golang:1.19-alpine

# Set the working directory inside the container
WORKDIR /app/api

# Copy the built Go binary from the first stage
RUN apk add git
RUN git clone https://github.com/Threqt1/HACApi.git HACApi
COPY .env ./HACApi/.env


# Expose any necessary ports
EXPOSE 3000

WORKDIR /app/api/HACApi
RUN go mod download
