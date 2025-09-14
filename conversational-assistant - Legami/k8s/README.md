Kubernetes (Docker Desktop) quickstart

1) Enable Kubernetes in Docker Desktop (Preferences → Kubernetes → Enable) and wait until it’s running.
2) Build the image locally:
   docker build -t conversational-assistant:latest ..
   (Run from the conversational-assistant folder.)
3) Apply namespace and secret:
   kubectl apply -f k8s/namespace.yaml
   kubectl create secret generic openai-api \
     --from-literal=OPENAI_API_KEY="$OPENAI_API_KEY" \
     -n conversational-assistant
   (Set OPENAI_API_KEY in your shell first or edit k8s/secret.template.yaml and apply it.)
4) Deploy app and service:
   kubectl apply -f k8s/deployment.yaml
   kubectl rollout status deployment/conv-assistant -n conversational-assistant
5) Access the app:
   NodePort: http://localhost:30080

