source .env.github

echo ${USER}
echo ${TOKEN} | docker login ghcr.io -u ${USER} --password-stdin
# docker login ghcr.io -u ${USER}