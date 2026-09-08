#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Planfile CI/CD Runner${NC}"
echo "=============================="

# The fleet runner no longer downloads or embeds Ollama. Call an external,
# independently managed Ollama endpoint through the normal provider settings.
if [ "${ENABLE_OLLAMA:-false}" = "true" ]; then
    echo -e "${RED}❌ Embedded Ollama is not part of the locked runner image.${NC}" >&2
    echo "Configure an external Ollama endpoint instead." >&2
    exit 2
fi

# Check required environment variables
check_env() {
    local var=$1
    local desc=$2
    
    if [ -z "${!var}" ]; then
        echo -e "${RED}❌ $var not set ($desc)${NC}"
        return 1
    else
        echo -e "${GREEN}✅ $var configured${NC}"
        return 0
    fi
}

# Validate configuration
validate_config() {
    echo -e "${YELLOW}🔍 Validating configuration...${NC}"
    
    local errors=0
    
    # Check strategy file
    if [ -n "$STRATEGY_FILE" ]; then
        if [ -f "$STRATEGY_FILE" ]; then
            echo -e "${GREEN}✅ Strategy file found: $STRATEGY_FILE${NC}"
        else
            echo -e "${RED}❌ Strategy file not found: $STRATEGY_FILE${NC}"
            errors=$((errors + 1))
        fi
    fi
    
    # Check backends
    if [ -n "$BACKENDS" ]; then
        IFS=',' read -ra BACKEND_ARRAY <<< "$BACKENDS"
        for backend in "${BACKEND_ARRAY[@]}"; do
            case $backend in
                "github")
                    check_env "GITHUB_TOKEN" "GitHub token" || errors=$((errors + 1))
                    check_env "GITHUB_REPO" "GitHub repository" || errors=$((errors + 1))
                    ;;
                "jira")
                    check_env "JIRA_URL" "Jira URL" || errors=$((errors + 1))
                    check_env "JIRA_EMAIL" "Jira email" || errors=$((errors + 1))
                    check_env "JIRA_TOKEN" "Jira token" || errors=$((errors + 1))
                    check_env "JIRA_PROJECT" "Jira project" || errors=$((errors + 1))
                    ;;
                "gitlab")
                    check_env "GITLAB_TOKEN" "GitLab token" || errors=$((errors + 1))
                    check_env "GITLAB_PROJECT_ID" "GitLab project ID" || errors=$((errors + 1))
                    ;;
            esac
        done
    fi
    
    if [ $errors -gt 0 ]; then
        echo -e "${RED}❌ Configuration validation failed with $errors errors${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Configuration valid${NC}"
}

# Setup workspace
setup_workspace() {
    echo -e "${YELLOW}📁 Setting up workspace...${NC}"
    
    # Create workspace directory if not exists
    mkdir -p "$WORKSPACE"
    
    # Copy strategy file if provided
    if [ -n "$STRATEGY_FILE" ] && [ -f "$STRATEGY_FILE" ]; then
        cp "$STRATEGY_FILE" "$WORKSPACE/planfile.yaml"
        echo -e "${GREEN}✅ Strategy copied to workspace${NC}"
    fi
    
    # Change to workspace directory
    cd "$WORKSPACE"
    
    # Initialize git if needed
    if [ ! -d .git ] && [ -n "$GIT_REPO" ]; then
        echo -e "${YELLOW}📥 Cloning repository...${NC}"
        git clone "$GIT_REPO" .
    fi
}

# Run the command
run_command() {
    echo -e "${YELLOW}🏃 Running command: $@${NC}"
    
    # Build planfile command
    local cmd="planfile"
    
    # Add command arguments
    if [ -n "$MAX_ITERATIONS" ]; then
        cmd="$cmd --max-iterations $MAX_ITERATIONS"
    fi
    
    if [ "$AUTO_FIX" = "true" ]; then
        cmd="$cmd --auto-fix"
    fi
    
    if [ -n "$BACKENDS" ]; then
        IFS=',' read -ra BACKEND_ARRAY <<< "$BACKENDS"
        for backend in "${BACKEND_ARRAY[@]}"; do
            cmd="$cmd --backend $backend"
        done
    fi
    
    if [ -n "$OUTPUT_FILE" ]; then
        cmd="$cmd --output $OUTPUT_FILE"
    fi
    
    # Add strategy file if exists
    if [ -f "planfile.yaml" ]; then
        cmd="$cmd planfile.yaml"
    fi
    
    # Add project path
    cmd="$cmd ."
    
    # Execute
    echo -e "${GREEN}Executing: $cmd${NC}"
    exec $cmd "$@"
}

# Main execution
main() {
    # Print environment info
    echo "Environment:"
    echo "  Python: $(python --version)"
    echo "  Planfile: $(planfile --version)"
    echo "  Workspace: $WORKSPACE"
    echo "  Results: $RESULTS_DIR"
    echo ""
    
    # Validate configuration
    validate_config
    
    # Setup workspace
    setup_workspace
    
    # Run the command
    run_command "$@"
}

# Handle signals
trap 'echo -e "\n${YELLOW}🛑 Interrupted${NC}"; exit 130' INT TERM

# Run main function
main "$@"
