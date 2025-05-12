# Use Python 3.13 Alpine image
FROM python:3.13-alpine

# Install dependencies for Microsoft ODBC Driver, Git, and build tools
RUN apk add --no-cache \
    curl \
    bash \
    icu-libs \
    krb5-libs \
    libgcc \
    libstdc++ \
    libssl3 \
    unixodbc \
    unixodbc-dev \
    gnupg \
    git \
    g++ \
    make \
    musl-dev \
    && case $(uname -m) in \
        x86_64) architecture="amd64" ;; \
        arm64) architecture="arm64" ;; \
        *) architecture="unsupported" ;; \
    esac \
    && if [ "$architecture" = "unsupported" ]; then \
        echo "Alpine architecture $(uname -m) is not currently supported." && exit 1; \
    fi \
    && curl -O https://download.microsoft.com/download/fae28b9a-d880-42fd-9b98-d779f0fdd77f/msodbcsql18_18.5.1.1-1_$architecture.apk \
    && curl -O https://download.microsoft.com/download/7/6/d/76de322a-d860-4894-9945-f0cc5d6a45f8/mssql-tools18_18.4.1.1-1_$architecture.apk \
    && curl -O https://download.microsoft.com/download/fae28b9a-d880-42fd-9b98-d779f0fdd77f/msodbcsql18_18.5.1.1-1_$architecture.sig \
    && curl -O https://download.microsoft.com/download/7/6/d/76de322a-d860-4894-9945-f0cc5d6a45f8/mssql-tools18_18.4.1.1-1_$architecture.sig \
    && curl https://packages.microsoft.com/keys/microsoft.asc | gpg --import - \
    && gpg --verify msodbcsql18_18.5.1.1-1_$architecture.sig msodbcsql18_18.5.1.1-1_$architecture.apk \
    && gpg --verify mssql-tools18_18.4.1.1-1_$architecture.sig mssql-tools18_18.4.1.1-1_$architecture.apk \
    && apk add --allow-untrusted msodbcsql18_18.5.1.1-1_$architecture.apk \
    && apk add --allow-untrusted mssql-tools18_18.4.1.1-1_$architecture.apk \
    && rm -f msodbcsql18_18.5.1.1-1_$architecture.* mssql-tools18_18.4.1.1-1_$architecture.*

# Set working directory
WORKDIR /app

# Clone the public GitHub repository
RUN git clone https://github.com/KasaCompaniesIT/abaswebapp.git .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8000

# Run Gunicorn
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:8000", "app:app"]