# Delivery Route Optimization System

DevOps & Agile Methodologies (23AD52C) mini project - MUTHUKUMAR G (24243006), AI & DS, National Engineering College.

A Flask web app that stores a depot and delivery locations, computes the shortest round-trip delivery route
(Nearest Neighbour + 2-Opt on Haversine distances), and reports distance, time and fuel savings.

## Run
    pip install -r requirements.txt
    python app.py            # http://localhost:5000  (admin / admin123)

## Test
    pytest -v

## Docker
    docker compose up --build
