source .env.github

SECRET=$(echo -n "$USER:$TOKEN" | base64)
echo $SECRET

AS_JSON='{
    "auths":
    {
        "ghcr.io":
            {
                "auth":"'${SECRET}'"
            }
    }
}'
echo $AS_JSON

B64=$(echo -n  $AS_JSON | base64)
echo $B64

echo '''
kind: Secret
type: kubernetes.io/dockerconfigjson
apiVersion: v1
metadata:
  name: ghcr-login-whitecap
  labels:
    app: app-name
data:
  .dockerconfigjson: '$B64'
''' >> /tmp/b64_ghcr_secret.yaml

cat /tmp/b64_ghcr_secret.yaml

kubectl delete -f /tmp/b64_ghcr_secret.yaml
kubectl create -f /tmp/b64_ghcr_secret.yaml
rm /tmp/b64_ghcr_secret.yaml
