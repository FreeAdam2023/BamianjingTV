pipeline {
    agent { label 'GPU-Worker' }

    parameters {
        choice(
            name: 'DEPLOY_TARGET',
            choices: ['app', 'ue5', 'all'],
            description: '''
            app (默认): 只部署 SceneMind API + Frontend (Docker)
            ue5: 只部署 UE5 虚拟演播室渲染服务
            all: 部署全部
            '''
        )
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
        booleanParam(
            name: 'UE5_SKIP_PACKAGE',
            defaultValue: true,
            description: 'UE5: 跳过打包，直接部署已有构建产物'
        )
    }

    environment {
        PROJECT_DIR       = '/home/adamlyu/BamianjingTV'
        COMPOSE_FILE      = 'docker-compose.yml'
        DOCKER_BUILDKIT   = '1'
        COMPOSE_DOCKER_CLI_BUILD = '1'
        // UE5 paths
        UE5_ENGINE_DIR    = '/opt/UnrealEngine'
        UE5_PROJECT_DIR   = '/home/adamlyu/VirtualStudio'
        UE5_DEPLOY_DIR    = '/opt/virtual-studio'
        UE5_SERVICE_NAME  = 'virtual-studio'
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

        // ============ App Deployment (Docker) ============

        stage('Build Images') {
            when {
                expression { params.DEPLOY_TARGET in ['app', 'all'] }
            }
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

        stage('Deploy App') {
            when {
                expression { params.DEPLOY_TARGET in ['app', 'all'] }
            }
            steps {
                dir("${PROJECT_DIR}") {
                    sh '''
                        echo "Deploying API + Frontend..."
                        docker compose up -d --force-recreate api frontend
                    '''
                }
            }
        }

        stage('App Health Check') {
            when {
                expression { params.DEPLOY_TARGET in ['app', 'all'] }
            }
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

        // ============ UE5 Virtual Studio Deployment ============

        stage('Deploy UE5') {
            when {
                expression { params.DEPLOY_TARGET in ['ue5', 'all'] }
            }
            steps {
                dir("${PROJECT_DIR}") {
                    script {
                        try {
                            def skipFlag = params.UE5_SKIP_PACKAGE ? '--skip-package' : ''
                            sh """
                                echo "Deploying UE5 Virtual Studio..."
                                bash deploy/deploy-ue5.sh ${skipFlag}
                            """
                        } catch (err) {
                            if (params.DEPLOY_TARGET == 'all') {
                                echo "WARNING: UE5 deploy failed (non-fatal when target=all): ${err.message}"
                                unstable('UE5 deploy failed but app deploy succeeded')
                            } else {
                                throw err
                            }
                        }
                    }
                }
            }
        }

        stage('UE5 Health Check') {
            when {
                expression { params.DEPLOY_TARGET in ['ue5', 'all'] }
            }
            steps {
                script {
                    echo "Checking UE5 service status..."

                    // Check systemd service
                    def serviceStatus = sh(
                        script: "systemctl is-active ${UE5_SERVICE_NAME} || echo 'inactive'",
                        returnStdout: true
                    ).trim()
                    echo "UE5 service: ${serviceStatus}"

                    if (serviceStatus != 'active') {
                        echo "WARNING: UE5 service is not active. Check: sudo journalctl -u ${UE5_SERVICE_NAME} -f"
                    }

                    // Check Remote Control API
                    def ue5Api = sh(
                        script: 'curl -sf http://localhost:30010/api/v1/preset -o /dev/null -w "%{http_code}" || echo "000"',
                        returnStdout: true
                    ).trim()
                    echo "UE5 Remote Control API: HTTP ${ue5Api}"

                    // Check SceneMind studio proxy
                    def studioStatus = sh(
                        script: 'curl -sf http://localhost:8001/studio/status || echo "FAILED"',
                        returnStdout: true
                    ).trim()

                    if (studioStatus != 'FAILED') {
                        echo "SceneMind /studio/status OK"
                    } else {
                        echo "WARNING: SceneMind /studio/status not responding (API may not be running)"
                    }
                }
            }
        }

        // ============ Cleanup ============

        stage('Cleanup') {
            when {
                expression { params.DEPLOY_TARGET in ['app', 'all'] }
            }
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
                def target = params.DEPLOY_TARGET
                echo "Deployment successful! (target: ${target}, mode: ${params.DEPLOY_MODE})"
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
