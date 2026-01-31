#!/bin/bash

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 2
    done

    echo "PostgreSQL started"
fi

# создаём базу и процесс, который не даст контейнеру закрыться
python create_db.py && tail -f /dev/null

exec "$@"
