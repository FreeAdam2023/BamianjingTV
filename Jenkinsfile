pipeline {
    agent { label 'GPU-Worker' }

    environment {
        PROJECT_DIR = '/home/adamlyu/BamianjingTV'
        COMPOSE_FILE = 'docker-compose.yml'
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                dir("${PROJECT_DIR}") {
                    checkout scm
                }
            }
        }

        stage('Build Images') {
            steps {
                dir("${PROJECT_DIR}") {
                    sh '''
                        echo "Building Docker images..."
                        docker compose build --no-cache api frontend
                    '''
                }
            }
        }

        stage('Deploy') {
            steps {
                dir("${PROJECT_DIR}") {
                    sh '''
                        echo "Deploying services..."
                        docker compose up -d --force-recreate api frontend
                    '''
                }
            }
        }

        stage('Health Check') {
            steps {
                script {
                    sleep 15
                    def response = sh(
                        script: 'curl -sf http://localhost:8000/stats || echo "FAILED"',
                        returnStdout: true
                    ).trim()

                    if (response == 'FAILED') {
                        error('Health check failed - API not responding')
                    }
                    echo "Health check passed: ${response}"
                }
            }
        }

        stage('Cleanup') {
            steps {
                sh '''
                    echo "Cleaning up old images..."
                    docker image prune -f || true
                '''
            }
        }
    }

    post {
        success {
            echo '✅ Deployment successful!'
        }
        failure {
            echo '❌ Deployment failed!'
            // 可选: 发送通知
            // slackSend channel: '#deploys', message: "BamianjingTV deployment failed: ${env.BUILD_URL}"
        }
        always {
            cleanWs()
        }
    }
}
