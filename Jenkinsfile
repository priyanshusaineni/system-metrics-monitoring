pipeline {
    agent any

    environment {
        DOCKER_HUB_USERNAME = 'priyanshu0811'
        IMAGE = "${DOCKER_HUB_USERNAME}/backend11:latest"
        KUBE_CONFIG = credentials('kube-credentials-id')
    }

    stages {

        stage('Build and Push Images to Docker Hub') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'DOCKERHUB_CRED', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
                    sh 'cd backend'
                    sh 'docker build -t $IMAGE -f backend/Dockerfile .'                
                    sh 'echo $DOCKER_PASS | docker login -u $DOCKER_USER --password-stdin'
                    sh 'docker push $IMAGE'
                }
            }
        }

        stage('Deploy to Kubernetes') {
            environment {
                POSTGRES_USER = credentials('postgres-user')         
                POSTGRES_PASSWORD = credentials('postgres-password') 
            }

            steps {
                withCredentials([file(credentialsId: 'kube-config-file', variable: 'KUBECONFIG')]) {
                    sh '''                    
                    # Create DB secret
                    kubectl create secret generic postgres-db-secrets \
                      --from-literal=POSTGRES_USER=$POSTGRES_USER \
                      --from-literal=POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
                      --dry-run=client -o yaml | kubectl apply -f -

                    # Apply all manifests
                    kubectl apply -f kubes/
                    '''
                }
            }
        }
    }
}