#!/bin/bash
set -e
GIT_REPO_URL="https://github.com/MakeWithArpit/attendance.git"

mkdir -p project
cd project
git clone "$GIT_REPO_URL"
cd attendance/Backend/attendance_system
chmod +x scripts/*.sh

# Execute scripts for OS dependencies, Python dependencies, Gunicorn, Nginx, and starting the application
./scripts/instance_os_dependencies.sh
./scripts/python_dependencies.sh
./scripts/gunicorn.sh
./scripts/nginx.sh
./scripts/start_app.sh
