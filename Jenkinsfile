#!groovy
@Library("ds-utils@v0.2.0") // Uses library from https://github.com/UIUCLibrary/Jenkins_utils
import org.ds.*
pipeline {
    agent {
        label "Windows&&DevPi"
    }
    
    triggers {
        cron('@daily')
    }

    options {
        disableConcurrentBuilds()  //each branch has 1 job running at a time
    }

    environment {
        mypy_args = "--junit-xml=mypy.xml"
        build_number = VersionNumber(projectStartDate: '2017-11-08', versionNumberString: '${BUILD_DATE_FORMATTED, "yy"}${BUILD_MONTH, XX}${BUILDS_THIS_MONTH, XXX}', versionPrefix: '', worstResultForIncrement: 'SUCCESS')
        // pytest_args = "--junitxml=reports/junit-{env:OS:UNKNOWN_OS}-{envname}.xml --junit-prefix={env:OS:UNKNOWN_OS}  --basetemp={envtmpdir}"
    }

    parameters {
        string(name: "PROJECT_NAME", defaultValue: "Speedwagon", description: "Name given to the project")
        booleanParam(name: "UPDATE_JIRA_EPIC", defaultValue: false, description: "Write a Update information on JIRA board")
        string(name: 'JIRA_ISSUE', defaultValue: "PSR-83", description: 'Jira task to generate about updates.')
        booleanParam(name: "UNIT_TESTS", defaultValue: true, description: "Run automated unit tests")
        booleanParam(name: "ADDITIONAL_TESTS", defaultValue: true, description: "Run additional tests")
        booleanParam(name: "PACKAGE", defaultValue: true, description: "Create a package")
        booleanParam(name: "DEPLOY_DEVPI", defaultValue: true, description: "Deploy to devpi on https://devpi.library.illinois.edu/DS_Jenkins/${env.BRANCH_NAME}")
        choice(choices: 'None\nRelease_to_devpi_only\nRelease_to_devpi_and_sccm\n', description: "Release the build to production. Only available in the Master branch", name: 'RELEASE')
        booleanParam(name: "UPDATE_DOCS", defaultValue: false, description: "Update online documentation")
        string(name: 'URL_SUBFOLDER', defaultValue: "speedwagon", description: 'The directory that the docs should be saved under')
    }
    
    stages {
        stage("Testing Jira epic"){
            agent any
            when {
                expression {params.UPDATE_JIRA_EPIC == true}
            }
            steps {
                echo "Finding Jira epic"
                script {
                    // def result = jiraSearch "issue = $params.JIRA_ISSUE"
                    // jiraComment body: 'Just a test', issueKey: 'PSR-83'
                    def result = jiraGetIssue idOrKey: 'PSR-83', site: 'https://bugs.library.illinois.edu'
                    echo "result = ${result}"
                    // def result = jiraIssueSelector(issueSelector: [$class: 'DefaultIssueSelector'])
                    // def result = jiraIssueSelector(issueSelector: [$class: 'JqlIssueSelector', jql: "issue = $params.JIRA_ISSUE"])
                    // if(result.isEmpty()){
                    //     echo "Jira issue not found"
                    //     error("Jira issue not found")

                    // } else {
                    //     echo "Located ${result}"
                    // }
                }

            }
        }

        stage("Cloning Source") {
            steps {
                deleteDir()
                checkout scm
                stash includes: '**', name: "Source", useDefaultExcludes: false
                stash includes: 'deployment.yml', name: "Deployment"
            }

        }
        stage("Unit Tests") {
            when {
                expression { params.UNIT_TESTS == true }
            }    
            parallel{
                stage("PyTest") {
                    agent {
                        node {
                            label "Windows&&Python3"
                        }
                    }
                    steps{
                        checkout scm
                        // bat "${tool 'Python3.6.3_Win64'} -m tox -e py36"
                        bat "${tool 'Python3.6.3_Win64'} -m tox -e pytest -- --junitxml=reports/junit-${env.NODE_NAME}-pytest.xml --junit-prefix=${env.NODE_NAME}-pytest" //  --basetemp={envtmpdir}" 
                        junit "reports/junit-${env.NODE_NAME}-pytest.xml"
                        }
                }
                stage("Behave") {
                    agent {
                        node {
                            label "Windows&&Python3"
                        }
                    }
                    steps {
                        checkout scm
                        bat "${tool 'Python3.6.3_Win64'} -m tox -e bdd --  --junit --junit-directory reports" 
                        junit "reports/*.xml"
                    }
                }
            }
        }
        stage("Additional Tests") {
            when {
                expression { params.ADDITIONAL_TESTS == true }
            }

            parallel {
                stage("Documentation"){
                    agent {
                        node {
                            label "Windows&&Python3"
                        }
                    }
                    steps {
                        checkout scm
                        bat "${tool 'Python3.6.3_Win64'} -m tox -e docs"
                        script{
                            // Multibranch jobs add the slash and add the branch to the job name. I need only the job name
                            def alljob = env.JOB_NAME.tokenize("/") as String[]
                            def project_name = alljob[0]
                            dir('.tox/dist') {
                                zip archive: true, dir: 'html', glob: '', zipFile: "${project_name}-${env.BRANCH_NAME}-docs-html-${env.GIT_COMMIT.substring(0,6)}.zip"
                                dir("html"){
                                    stash includes: '**', name: "HTML Documentation"
                                }
                            }
                        }
                    }
                }
                stage("MyPy") {
                    agent {
                        node {
                            label "Windows&&Python3"
                        }
                    }
                    steps{
                        checkout scm
                        bat "${tool 'Python3.6.3_Win64'} -m venv venv"
                        bat "venv\\Scripts\\pip.exe install mypy lxml"
                        bat 'mkdir "reports/mypy/stdout"'
                        bat returnStatus: true, script: "venv\\Scripts\\mypy.exe speedwagon --html-report reports\\mypy\\html\\ > reports/mypy/stdout/mypy.txt"
                    }
                    post {
                        always {
                            warnings parserConfigurations: [[parserName: 'MyPy', pattern: 'reports\\mypy\\stdout\\mypy.txt']], unHealthy: ''
                            publishHTML([allowMissing: false, alwaysLinkToLastBuild: false, keepAll: false, reportDir: 'reports/mypy/html/', reportFiles: 'index.html', reportName: 'MyPy HTML Report', reportTitles: ''])
                        }
                    }
                }
                stage("Flake8") {
                    agent {
                        node {
                            label "Windows&&Python3"
                        }
                    }
                    steps{
                        checkout scm
                        bat "${tool 'Python3.6.3_Win64'} -m venv venv"
                        bat "venv\\Scripts\\pip.exe install flake8"
                        bat returnStatus: true, script: "venv\\Scripts\\flake8.exe speedwagon --output-file=reports\\flake8.txt --format=pylint"
                    } 
                    post{
                        always {
                            warnings parserConfigurations: [[parserName: 'PyLint', pattern: 'reports/flake8.txt']], unHealthy: ''
                        }                        
                    }
                }

            }

        }

        stage("Packaging") {
            when {
                expression { params.PACKAGE == true }
            }

            parallel {
                stage("Source and Wheel formats"){
                    steps{
                        bat "call make.bat"
                    }
                    post {
                        always {
                            dir("dist") {
                                archiveArtifacts artifacts: "*.whl", fingerprint: true
                                archiveArtifacts artifacts: "*.tar.gz", fingerprint: true
                                archiveArtifacts artifacts: "*.zip", fingerprint: true
                            }
                        }
                    }
                }
                stage("Windows Standalone"){
                    agent {
                        node {
                            label "Windows&&VS2015&&DevPi"
                        }
                    }
                    when { not { changeRequest() }}
                    steps {
                        deleteDir()
                        unstash "Source"
                        bat "call make.bat standalone"
                        dir("dist") {
                            stash includes: "*.msi", name: "msi"
                        }
                    }
                    post {
                        success {
                            dir("dist") {
                                archiveArtifacts artifacts: "*.msi", fingerprint: true
                            }
                        }
                    }
                }
            }

        }

        stage("Deploying to Devpi") {
            when {
                expression { params.DEPLOY_DEVPI == true && (env.BRANCH_NAME == "master" || env.BRANCH_NAME == "dev")}
            }
            steps {
                bat "${tool 'Python3.6.3_Win64'} -m devpi use https://devpi.library.illinois.edu"
                withCredentials([usernamePassword(credentialsId: 'DS_devpi', usernameVariable: 'DEVPI_USERNAME', passwordVariable: 'DEVPI_PASSWORD')]) {
                    bat "${tool 'Python3.6.3_Win64'} -m devpi login ${DEVPI_USERNAME} --password ${DEVPI_PASSWORD}"
                    bat "${tool 'Python3.6.3_Win64'} -m devpi use /${DEVPI_USERNAME}/${env.BRANCH_NAME}_staging"
                    script {
                        bat "${tool 'Python3.6.3_Win64'} -m devpi upload --from-dir dist"
                        try {
                            bat "${tool 'Python3.6.3_Win64'} -m devpi upload --only-docs"
                        } catch (exc) {
                            echo "Unable to upload to devpi with docs."
                        }
                    }
                }

            }
        }
        stage("Test DevPi packages") {
            when {
                expression { params.DEPLOY_DEVPI == true && (env.BRANCH_NAME == "master" || env.BRANCH_NAME == "dev")}
            }
            parallel {
                stage("Source Distribution: .tar.gz") {
                    steps {
                        script {
                            def name = bat(returnStdout: true, script: "@${tool 'Python3.6.3_Win64'} setup.py --name").trim()
                            def version = bat(returnStdout: true, script: "@${tool 'Python3.6.3_Win64'} setup.py --version").trim()
                            node("Windows&&DevPi") {
                                withCredentials([usernamePassword(credentialsId: 'DS_devpi', usernameVariable: 'DEVPI_USERNAME', passwordVariable: 'DEVPI_PASSWORD')]) {
                                    bat "${tool 'Python3.6.3_Win64'} -m devpi login ${DEVPI_USERNAME} --password ${DEVPI_PASSWORD}"
                                    bat "${tool 'Python3.6.3_Win64'} -m devpi use /${DEVPI_USERNAME}/${env.BRANCH_NAME}_staging"
                                    echo "Testing Source package in devpi"
                                    bat "${tool 'Python3.6.3_Win64'} -m devpi test --index https://devpi.library.illinois.edu/${DEVPI_USERNAME}/${env.BRANCH_NAME}_staging ${name} -s tar.gz"
                                }
                            }
                        }
                    }
                }
                stage("Source Distribution: .zip") {
                    steps {
                        script {
                            def name = bat(returnStdout: true, script: "@${tool 'Python3.6.3_Win64'} setup.py --name").trim()
                            def version = bat(returnStdout: true, script: "@${tool 'Python3.6.3_Win64'} setup.py --version").trim()
                            node("Windows&&DevPi") {
                                withCredentials([usernamePassword(credentialsId: 'DS_devpi', usernameVariable: 'DEVPI_USERNAME', passwordVariable: 'DEVPI_PASSWORD')]) {
                                    bat "${tool 'Python3.6.3_Win64'} -m devpi login ${DEVPI_USERNAME} --password ${DEVPI_PASSWORD}"
                                    bat "${tool 'Python3.6.3_Win64'} -m devpi use /${DEVPI_USERNAME}/${env.BRANCH_NAME}_staging"
                                    echo "Testing Source package in devpi"
                                    bat "${tool 'Python3.6.3_Win64'} -m devpi test --index https://devpi.library.illinois.edu/${DEVPI_USERNAME}/${env.BRANCH_NAME}_staging ${name} -s zip"
                                }
                            }
                        }
                    }
                }
                stage("Built Distribution: .whl") {
                    steps {
                        script {
                            def name = bat(returnStdout: true, script: "@${tool 'Python3.6.3_Win64'} setup.py --name").trim()
                            def version = bat(returnStdout: true, script: "@${tool 'Python3.6.3_Win64'} setup.py --version").trim()
                            node("Windows&&DevPi") {
                                withCredentials([usernamePassword(credentialsId: 'DS_devpi', usernameVariable: 'DEVPI_USERNAME', passwordVariable: 'DEVPI_PASSWORD')]) {
                                    bat "${tool 'Python3.6.3_Win64'} -m devpi login ${DEVPI_USERNAME} --password ${DEVPI_PASSWORD}"
                                    bat "${tool 'Python3.6.3_Win64'} -m devpi use /${DEVPI_USERNAME}/${env.BRANCH_NAME}_staging"
                                    echo "Testing Whl package in devpi"
                                    bat " ${tool 'Python3.6.3_Win64'} -m devpi test --index https://devpi.library.illinois.edu/${DEVPI_USERNAME}/${env.BRANCH_NAME}_staging ${name} -s whl"
                                }
                            }
                        }

                    }
                }
            }
            post {
                success {
                    echo "it Worked. Pushing file to ${env.BRANCH_NAME} index"
                    script {
                        def name = bat(returnStdout: true, script: "@${tool 'Python3.6.3_Win64'} setup.py --name").trim()
                        def version = bat(returnStdout: true, script: "@${tool 'Python3.6.3_Win64'} setup.py --version").trim()
                        withCredentials([usernamePassword(credentialsId: 'DS_devpi', usernameVariable: 'DEVPI_USERNAME', passwordVariable: 'DEVPI_PASSWORD')]) {
                            bat "${tool 'Python3.6.3_Win64'} -m devpi login ${DEVPI_USERNAME} --password ${DEVPI_PASSWORD}"
                            bat "${tool 'Python3.6.3_Win64'} -m devpi use /${DEVPI_USERNAME}/${env.BRANCH_NAME}_staging"
                            bat "${tool 'Python3.6.3_Win64'} -m devpi push ${name}==${version} ${DEVPI_USERNAME}/${env.BRANCH_NAME}"
                        }

                    }
                }
            }
        }
        stage("Release to DevPi production") {
            when {
                expression { params.RELEASE != "None" && env.BRANCH_NAME == "master" }
            }
            steps {
                script {
                    def name = bat(returnStdout: true, script: "@${tool 'Python3.6.3_Win64'} setup.py --name").trim()
                    def version = bat(returnStdout: true, script: "@${tool 'Python3.6.3_Win64'} setup.py --version").trim()
                    withCredentials([usernamePassword(credentialsId: 'DS_devpi', usernameVariable: 'DEVPI_USERNAME', passwordVariable: 'DEVPI_PASSWORD')]) {
                        bat "${tool 'Python3.6.3_Win64'} -m devpi login ${DEVPI_USERNAME} --password ${DEVPI_PASSWORD}"
                        bat "${tool 'Python3.6.3_Win64'} -m devpi use /${DEVPI_USERNAME}/${env.BRANCH_NAME}_staging"
                        bat "${tool 'Python3.6.3_Win64'} -m devpi push ${name}==${version} production/release"
                    }

                }
                node("Linux"){
                    updateOnlineDocs url_subdomain: params.URL_SUBFOLDER, stash_name: "HTML Documentation"
                }
            }
        }

        stage("Deploy to SCCM") {
            when {
                expression { params.RELEASE == "Release_to_devpi_and_sccm"}
            }

            steps {
                node("Linux"){
                    unstash "msi"
                    deployStash("msi", "${env.SCCM_STAGING_FOLDER}/${params.PROJECT_NAME}/")
                    input("Deploy to production?")
                    deployStash("msi", "${env.SCCM_UPLOAD_FOLDER}")
                }

            }
            post {
                success {
                    script{
                        def  deployment_request = requestDeploy this, "deployment.yml"
                        echo deployment_request
                        writeFile file: "deployment_request.txt", text: deployment_request
                        archiveArtifacts artifacts: "deployment_request.txt"
                    }
                }
            }
        }
        stage("Update online documentation") {
            agent {
                label "Linux"
            }
            when {
              expression {params.UPDATE_DOCS == true }
            }
            steps {
                updateOnlineDocs url_subdomain: params.URL_SUBFOLDER, stash_name: "HTML Documentation"
            }
            post {
                success {
                    script {
                        echo "https://www.library.illinois.edu/dccdocs/${params.URL_SUBFOLDER} updated successfully."
                    }
                }
            }

        }
    }
    post {
        always {
            script {
                if (env.BRANCH_NAME == "master" || env.BRANCH_NAME == "dev"){
                    def name = bat(returnStdout: true, script: "@${tool 'Python3.6.3_Win64'} setup.py --name").trim()
                    def version = bat(returnStdout: true, script: "@${tool 'Python3.6.3_Win64'} setup.py --version").trim()
                    withCredentials([usernamePassword(credentialsId: 'DS_devpi', usernameVariable: 'DEVPI_USERNAME', passwordVariable: 'DEVPI_PASSWORD')]) {
                        bat "${tool 'Python3.6.3_Win64'} -m devpi login ${DEVPI_USERNAME} --password ${DEVPI_PASSWORD}"
                        bat "${tool 'Python3.6.3_Win64'} -m devpi use /${DEVPI_USERNAME}/${env.BRANCH_NAME}_staging"
                        bat "${tool 'Python3.6.3_Win64'} -m devpi remove -y ${name}==${version}"
                    }
                }
            }
        }
        success {
            echo "Cleaning up workspace"
            deleteDir()
        }
    }
}
