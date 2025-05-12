if [ -d "./app/.git" ]; then
    echo "Repository exists. Pulling latest changes..."
    cd ./app
    git pull origin main
    cd ..
else
    echo "Repository does not exist. Cloning..."
    git clone https://github.com/KasaCompaniesIT/abaswebapp.git ./app
fi

echo "Restarting Docker containers..."
docker-compose down
docker-compose up --build -d