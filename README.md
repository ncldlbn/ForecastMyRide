 
# Setup
Make sure you have *git* and *Docker* installed. 


Clone the repository:

```
git clone https://github.com/ncldlbn/ForecastMyRide.git
```

Build docker image:
```
docker build -t forecastmyride-img .
```

# Run
Run the container:
```
docker run -d -p 8501:8501 --name forecastmyride-app forecastmyride-img
```

View the app at `http://localhost:8501`

---

Run the container in development mode:
```
docker run -it --rm -v "$PWD":/app -p 8501:8501 -w /app forecastmyride-img
```

Stop and run the container after first launch
```
docker stop forecastmyride-app
docker start forecastmyride-app
```