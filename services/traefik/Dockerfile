FROM traefik:v2.11

COPY traefik.yml /etc/traefik/traefik.yml
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
