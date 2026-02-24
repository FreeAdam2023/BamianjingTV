pipeline {
    agent { label 'GPU-Worker' }

    parameters {
        choice(
            name: 'DEPLOY_MODE',
            choices: ['quick', 'full'],
            description: '''
            quick (默认): 利用 Docker 缓存，只重建变更的层，快速部署
            full: 拉取最新基础镜像，依赖层仍利用缓存
            '''
        )
        booleanParam(
            name: 'SKIP_TESTS',
            defaultValue: true,
            description: '跳过测试阶段（快速部署时默认跳过）'
        )
    }

    environment {
        PROJECT_DIR       = '/home/adamlyu/BamianjingTV'
        COMPOSE_FILE      = 'docker-compose.yml'
        DOCKER_BUILDKIT   = '1'
        COMPOSE_DOCKER_CLI_BUILD = '1'
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 60, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                dir("${PROJECT_DIR}") {
                    retry(3) {
                        checkout scm
                    }
                }
            }
        }

        stage('Build Images') {
            steps {
                dir("${PROJECT_DIR}") {
                    script {
                        def buildArgs = ''
                        if (params.DEPLOY_MODE == 'full') {
                            echo "Full Build: Pulling fresh base images..."
                            buildArgs = '--pull'
                        } else {
                            echo "Quick Build: Using Docker cache..."
                            buildArgs = ''
                        }

                        sh """
                            echo "Build mode: ${params.DEPLOY_MODE}"
                            docker compose build ${buildArgs} api frontend
                        """
                    }
                }
            }
        }

        stage('Deploy') {
            steps {
                dir("${PROJECT_DIR}") {
                    sh '''
                        echo "Deploying API + Frontend..."
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
                        script: 'curl -sf http://localhost:8001/stats || echo "FAILED"',
                        returnStdout: true
                    ).trim()

                    if (response == 'FAILED') {
                        error('Health check failed - API not responding')
                    }
                    echo "API health check passed"
                }
            }
        }

        stage('Cleanup') {
            steps {
                script {
                    echo "Removing dangling images..."
                    sh 'docker image prune -f || true'
                }
            }
        }
    }

    post {
        success {
            script {
                echo "Deployment successful! (mode: ${params.DEPLOY_MODE})"
            }
        }
        failure {
            echo 'Deployment failed!'
        }
        always {
            cleanWs()
        }
    }
}
