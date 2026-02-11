pipeline {
    agent { label 'GPU-Worker' }

    // 参数化构建 - 支持快速部署和全新部署
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
        PROJECT_DIR = '/home/adamlyu/BamianjingTV'
        COMPOSE_FILE = 'docker-compose.yml'
        DOCKER_BUILDKIT = '1'
        COMPOSE_DOCKER_CLI_BUILD = '1'
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
                            echo "🔨 Full Build: Pulling fresh base images, layer cache for deps..."
                            buildArgs = '--pull'
                        } else {
                            echo "⚡ Quick Build: Using Docker cache for unchanged layers..."
                            buildArgs = ''
                        }

                        sh """
                            echo "Build mode: ${params.DEPLOY_MODE}"
                            echo "Build args: ${buildArgs}"
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
                        script: 'curl -sf http://localhost:8001/stats || echo "FAILED"',
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
                script {
                    echo "🧹 Removing dangling images..."
                    sh 'docker image prune -f || true'
                }
            }
        }
    }

    post {
        success {
            script {
                def modeEmoji = params.DEPLOY_MODE == 'quick' ? '⚡' : '🔨'
                echo "${modeEmoji} ✅ Deployment successful! (${params.DEPLOY_MODE} mode)"
            }
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
