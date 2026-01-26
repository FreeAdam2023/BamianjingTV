pipeline {
    agent { label 'GPU-Worker' }

    // 参数化构建 - 支持快速部署和全新部署
    parameters {
        choice(
            name: 'DEPLOY_MODE',
            choices: ['quick', 'full'],
            description: '''
            quick (默认): 利用 Docker 缓存，只重建变更的层，快速部署
            full: 清除缓存，从头构建所有镜像
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
                    script {
                        def buildArgs = ''
                        if (params.DEPLOY_MODE == 'full') {
                            echo "🔨 Full Build: Clearing cache, rebuilding all layers..."
                            buildArgs = '--no-cache --pull'
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
                script {
                    if (params.DEPLOY_MODE == 'full') {
                        echo "🧹 Full cleanup: Removing dangling images..."
                        sh 'docker image prune -af || true'
                    } else {
                        echo "🧹 Quick cleanup: Removing only dangling images..."
                        sh 'docker image prune -f || true'
                    }
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
