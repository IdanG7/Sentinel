#!/usr/bin/env groovy

/**
 * Sentinel Production Release Pipeline
 *
 * This pipeline builds, tests, signs, and publishes Sentinel artifacts.
 * Triggered on git tags (vX.Y.Z)
 */

pipeline {
    agent any

    environment {
        // Registry configuration
        DOCKER_REGISTRY = 'ghcr.io'
        REGISTRY_ORG = credentials('github-org')
        IMAGE_PREFIX = "${DOCKER_REGISTRY}/${REGISTRY_ORG}/sentinel"

        // Version extracted from git tag
        VERSION = sh(script: "git describe --tags --always", returnStdout: true).trim()

        // Tool versions
        PYTHON_VERSION = '3.11'
        GO_VERSION = '1.21'
        HELM_VERSION = '3.13.0'

        // Credentials
        DOCKER_CREDENTIALS = credentials('docker-registry-credentials')
        COSIGN_KEY = credentials('cosign-private-key')
        PYPI_CREDENTIALS = credentials('pypi-credentials')
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 60, unit: 'MINUTES')
        timestamps()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git fetch --tags'
            }
        }

        stage('Validate Version') {
            steps {
                script {
                    if (!env.VERSION.matches(/^v\d+\.\d+\.\d+$/)) {
                        error("Invalid version tag: ${env.VERSION}. Must match vX.Y.Z")
                    }
                    env.VERSION_NUMBER = env.VERSION.replaceAll(/^v/, '')
                }
            }
        }

        stage('Lint & Test') {
            parallel {
                stage('Python Lint') {
                    steps {
                        sh '''
                            for service in control-api pipeline-controller infra-adapter; do
                                echo "Linting services/$service..."
                                cd services/$service
                                pip install -e ".[dev]"
                                black --check .
                                ruff check .
                                mypy app/
                                cd ../..
                            done
                        '''
                    }
                }

                stage('Python Tests') {
                    steps {
                        sh '''
                            for service in control-api pipeline-controller infra-adapter; do
                                echo "Testing services/$service..."
                                cd services/$service
                                pytest tests/ -v --cov=app --cov-report=xml --cov-report=term
                                cd ../..
                            done
                        '''
                    }
                }

                stage('Go Lint & Test') {
                    steps {
                        sh '''
                            cd services/agent
                            go vet ./...
                            golangci-lint run
                            go test -v -race -coverprofile=coverage.txt ./...
                            cd ../..
                        '''
                    }
                }
            }
        }

        stage('Build Docker Images') {
            parallel {
                stage('Build Control API') {
                    steps {
                        script {
                            buildDockerImage('control-api')
                        }
                    }
                }

                stage('Build Pipeline Controller') {
                    steps {
                        script {
                            buildDockerImage('pipeline-controller')
                        }
                    }
                }

                stage('Build InfraMind Adapter') {
                    steps {
                        script {
                            buildDockerImage('infra-adapter')
                        }
                    }
                }

                stage('Build Agent') {
                    steps {
                        script {
                            buildDockerImage('agent')
                        }
                    }
                }
            }
        }

        stage('Security Scan') {
            parallel {
                stage('Trivy Scan') {
                    steps {
                        sh '''
                            for service in control-api pipeline-controller infra-adapter agent; do
                                echo "Scanning ${IMAGE_PREFIX}-${service}:${VERSION_NUMBER}..."
                                trivy image --severity HIGH,CRITICAL \
                                    --exit-code 1 \
                                    ${IMAGE_PREFIX}-${service}:${VERSION_NUMBER}
                            done
                        '''
                    }
                }

                stage('Grype Scan') {
                    steps {
                        sh '''
                            for service in control-api pipeline-controller infra-adapter agent; do
                                echo "Scanning with Grype: ${IMAGE_PREFIX}-${service}:${VERSION_NUMBER}..."
                                grype ${IMAGE_PREFIX}-${service}:${VERSION_NUMBER} \
                                    --fail-on high
                            done
                        '''
                    }
                }
            }
        }

        stage('Generate SBOM') {
            steps {
                sh '''
                    mkdir -p artifacts/sbom
                    for service in control-api pipeline-controller infra-adapter agent; do
                        echo "Generating SBOM for ${service}..."
                        syft ${IMAGE_PREFIX}-${service}:${VERSION_NUMBER} \
                            -o spdx-json \
                            > artifacts/sbom/${service}-sbom.spdx.json
                    done
                '''
                archiveArtifacts artifacts: 'artifacts/sbom/*.json', fingerprint: true
            }
        }

        stage('Sign Images') {
            steps {
                withCredentials([file(credentialsId: 'cosign-private-key', variable: 'COSIGN_KEY_FILE')]) {
                    sh '''
                        for service in control-api pipeline-controller infra-adapter agent; do
                            echo "Signing ${IMAGE_PREFIX}-${service}:${VERSION_NUMBER}..."
                            cosign sign --key ${COSIGN_KEY_FILE} \
                                ${IMAGE_PREFIX}-${service}:${VERSION_NUMBER}

                            # Attach SBOM attestation
                            cosign attach sbom --sbom artifacts/sbom/${service}-sbom.spdx.json \
                                ${IMAGE_PREFIX}-${service}:${VERSION_NUMBER}
                        done
                    '''
                }
            }
        }

        stage('Push Images') {
            steps {
                sh '''
                    docker login ${DOCKER_REGISTRY} -u ${DOCKER_CREDENTIALS_USR} -p ${DOCKER_CREDENTIALS_PSW}
                    for service in control-api pipeline-controller infra-adapter agent; do
                        echo "Pushing ${IMAGE_PREFIX}-${service}:${VERSION_NUMBER}..."
                        docker push ${IMAGE_PREFIX}-${service}:${VERSION_NUMBER}

                        # Tag as latest
                        docker tag ${IMAGE_PREFIX}-${service}:${VERSION_NUMBER} \
                            ${IMAGE_PREFIX}-${service}:latest
                        docker push ${IMAGE_PREFIX}-${service}:latest
                    done
                '''
            }
        }

        stage('Build Agent Binaries') {
            steps {
                sh '''
                    mkdir -p artifacts/binaries
                    cd services/agent

                    for os in linux darwin windows; do
                        for arch in amd64 arm64; do
                            if [ "$os" == "windows" ] && [ "$arch" == "arm64" ]; then
                                continue
                            fi

                            echo "Building for ${os}/${arch}..."
                            GOOS=$os GOARCH=$arch CGO_ENABLED=0 \
                                go build -ldflags="-w -s -X main.version=${VERSION_NUMBER}" \
                                -o ../../artifacts/binaries/sentinel-agent-${os}-${arch}$([ "$os" == "windows" ] && echo ".exe" || echo "") \
                                cmd/agent/main.go
                        done
                    done
                '''
                archiveArtifacts artifacts: 'artifacts/binaries/*', fingerprint: true
            }
        }

        stage('Package Helm Charts') {
            steps {
                sh '''
                    mkdir -p artifacts/helm
                    helm package charts/sentinel-core \
                        --version ${VERSION_NUMBER} \
                        --app-version ${VERSION_NUMBER} \
                        --destination artifacts/helm

                    helm package charts/sentinel-agent \
                        --version ${VERSION_NUMBER} \
                        --app-version ${VERSION_NUMBER} \
                        --destination artifacts/helm

                    helm package charts/obs-stack \
                        --version ${VERSION_NUMBER} \
                        --destination artifacts/helm
                '''
                archiveArtifacts artifacts: 'artifacts/helm/*.tgz', fingerprint: true
            }
        }

        stage('Publish Helm Charts') {
            steps {
                sh '''
                    # Push to OCI registry or Helm repository
                    for chart in artifacts/helm/*.tgz; do
                        echo "Publishing ${chart}..."
                        helm push ${chart} oci://${DOCKER_REGISTRY}/${REGISTRY_ORG}/charts
                    done
                '''
            }
        }

        stage('Build & Publish SDK') {
            when {
                expression { fileExists('sdk/sentinel-ops/pyproject.toml') }
            }
            steps {
                sh '''
                    cd sdk/sentinel-ops

                    # Update version in pyproject.toml
                    sed -i "s/version = .*/version = \\"${VERSION_NUMBER}\\"/" pyproject.toml

                    # Build wheel and sdist
                    python -m build

                    # Publish to PyPI
                    python -m twine upload dist/* \
                        --username ${PYPI_CREDENTIALS_USR} \
                        --password ${PYPI_CREDENTIALS_PSW}
                '''
            }
        }

        stage('Create GitHub Release') {
            steps {
                sh '''
                    # Generate changelog
                    PREV_TAG=$(git describe --tags --abbrev=0 HEAD~1 2>/dev/null || echo "")
                    if [ -n "$PREV_TAG" ]; then
                        CHANGELOG=$(git log --pretty=format:"- %s" ${PREV_TAG}..HEAD)
                    else
                        CHANGELOG="Initial release"
                    fi

                    # Create release
                    gh release create ${VERSION} \
                        --title "Sentinel ${VERSION}" \
                        --notes "${CHANGELOG}" \
                        artifacts/binaries/* \
                        artifacts/helm/*.tgz \
                        artifacts/sbom/*.json
                '''
            }
        }

        stage('Update Documentation') {
            steps {
                sh '''
                    # Update CHANGELOG.md
                    echo "## [${VERSION_NUMBER}] - $(date +%Y-%m-%d)" >> CHANGELOG.new
                    git log --pretty=format:"- %s" ${PREV_TAG:-HEAD}..HEAD >> CHANGELOG.new
                    echo "" >> CHANGELOG.new
                    cat CHANGELOG.md >> CHANGELOG.new
                    mv CHANGELOG.new CHANGELOG.md

                    # Commit and push
                    git add CHANGELOG.md
                    git commit -m "docs: update CHANGELOG for ${VERSION}" || true
                    git push origin HEAD:main
                '''
            }
        }
    }

    post {
        success {
            echo "✅ Release ${VERSION} completed successfully!"
            slackSend(
                color: 'good',
                message: "✅ Sentinel ${VERSION} released successfully!\nImages: ${IMAGE_PREFIX}-*:${VERSION_NUMBER}"
            )
        }

        failure {
            echo "❌ Release ${VERSION} failed!"
            slackSend(
                color: 'danger',
                message: "❌ Sentinel ${VERSION} release failed!\nCheck: ${BUILD_URL}"
            )
        }

        always {
            cleanWs()
        }
    }
}

// Helper function to build Docker images
def buildDockerImage(String service) {
    sh """
        docker build \
            -t ${IMAGE_PREFIX}-${service}:${VERSION_NUMBER} \
            -t ${IMAGE_PREFIX}-${service}:latest \
            --build-arg VERSION=${VERSION_NUMBER} \
            --label org.opencontainers.image.version=${VERSION_NUMBER} \
            --label org.opencontainers.image.created=\$(date -u +%Y-%m-%dT%H:%M:%SZ) \
            --label org.opencontainers.image.revision=\$(git rev-parse HEAD) \
            services/${service}
    """
}
