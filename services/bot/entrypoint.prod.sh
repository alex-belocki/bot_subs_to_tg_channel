#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 2
    done

    echo "PostgreSQL started"
fi

# python bot.py
python create_db.py

exec "$@"