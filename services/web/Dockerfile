# pull official base image
FROM python:3.12-slim-bookworm

# добавляем алиасы для удобства
RUN mkdir -p /root/.local/bin
ENV PATH="/root/.local/bin:${PATH}"
RUN echo 'export BOT=/usr/src/bot' >> /root/.bashrc && \
    echo 'export WEB=/usr/src/webapp' >> /root/.bashrc && \
    echo '# some more ls aliases' >> /root/.bashrc && \
    echo "alias ll='ls -alF'" >> /root/.bashrc && \
    echo "alias la='ls -A'" >> /root/.bashrc && \
    echo "alias l='ls -CF'" >> /root/.bashrc && \
    echo "alias cp='cp -i'" >> /root/.bashrc && \
    echo "alias df='df -h'" >> /root/.bashrc && \
    echo "alias free='free -m'" >> /root/.bashrc && \
    echo "alias np='nano -w PKGBUILD'" >> /root/.bashrc && \
    echo "alias more=less" >> /root/.bashrc && \
    echo "alias ll='ls -l'" >> /root/.bashrc && \
    echo "alias дд='ls -l'" >> /root/.bashrc && \
    echo "alias сдуфк='clear'" >> /root/.bashrc && \
    echo "alias учше='exit'" >> /root/.bashrc && \
    echo "alias back='source back'" >> /root/.bashrc && \
    echo "alias revision='alembic revision --autogenerate'" >> /root/.bashrc && \
    echo "alias upgrade='alembic upgrade head'" >> /root/.bashrc && \
    echo "alias stat='stat -c \"%a %n\"'" >> /root/.bashrc && \
    echo "alias bot='cd ${BOT} && clear && ll'" >> /root/.bashrc && \
    echo "alias web='cd ${WEB} && clear && ll'" >> /root/.bashrc && \
    echo 'if [ -f ~/.bash_aliases ]; then' >> /root/.bashrc && \
    echo '    . ~/.bash_aliases' >> /root/.bashrc && \
    echo 'fi' >> /root/.bashrc && \
    echo 'ds () {' >> /root/.bashrc && \
    echo '    echo "Disk Space Utilization For $HOSTNAME"' >> /root/.bashrc && \
    echo '    df -h' >> /root/.bashrc && \
    echo '}' >> /root/.bashrc

# set work directory
WORKDIR /usr/src/webapp

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Moscow

# install system dependencies
RUN apt-get update && apt-get install -y netcat-openbsd vim

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt /usr/src/webapp/requirements.txt
RUN pip install ipdb
RUN pip install -r requirements.txt

# copy project
COPY . /usr/src/webapp/

# run entrypoint.sh
ENTRYPOINT ["/usr/src/webapp/entrypoint.sh"]