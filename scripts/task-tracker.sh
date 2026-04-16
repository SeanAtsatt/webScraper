#!/bin/bash
# task-tracker.sh - Concurrent-safe task tracking system
# Uses per-task status files to avoid write conflicts

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Allow TASKS_BASE to be overridden via environment variable (for testing)
TASKS_BASE="${TASKS_BASE:-$PROJECT_ROOT/ai_working/tasks}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# =============================================================================
# Usage
# =============================================================================

usage() {
    local exit_code="${1:-0}"
    cat << 'EOF'
Usage: task-tracker.sh <command> [options]

Commands:
  init <name>              Initialize a new task list
  add <list> <subject>     Add a task to a list
  status <list> <id> <status>  Update task status (pending|in_progress|completed)
  block <list> <id> <blocked-by-id>  Add dependency
  view <list>              View task list with current status
  export <list>            Export to markdown

Status values:
  pending      - Not started
  in_progress  - Currently being worked on
  completed    - Done

Examples:
  task-tracker.sh init my-feature
  task-tracker.sh add my-feature "Implement login API"
  task-tracker.sh block my-feature 2 1        # Task 2 blocked by task 1
  task-tracker.sh status my-feature 1 completed
  task-tracker.sh view my-feature

EOF
    exit "$exit_code"
}

# =============================================================================
# Helper Functions
# =============================================================================

get_task_dir() {
    local list_name="$1"
    echo "$TASKS_BASE/$list_name"
}

ensure_task_dir() {
    local list_name="$1"
    local task_dir
    task_dir=$(get_task_dir "$list_name")
    mkdir -p "$task_dir/.status"
}

get_tasks_file() {
    local list_name="$1"
    echo "$(get_task_dir "$list_name")/tasks.json"
}

get_status_file() {
    local list_name="$1"
    local task_id="$2"
    echo "$(get_task_dir "$list_name")/.status/task-$(printf '%03d' "$task_id").status"
}

# =============================================================================
# Commands
# =============================================================================

cmd_init() {
    local list_name="${1:-}"

    if [[ -z "$list_name" ]]; then
        echo -e "${RED}Error: List name required${NC}" >&2
        usage 1
    fi

    ensure_task_dir "$list_name"
    local tasks_file
    tasks_file=$(get_tasks_file "$list_name")

    if [[ -f "$tasks_file" ]]; then
        echo -e "${YELLOW}Task list '$list_name' already exists${NC}"
        return 0
    fi

    # Initialize empty task list
    cat > "$tasks_file" << EOF
{
  "name": "$list_name",
  "created": "$(date -Iseconds)",
  "tasks": []
}
EOF

    echo -e "${GREEN}Created task list: $list_name${NC}"
    echo "Location: $tasks_file"
}

cmd_add() {
    local list_name="${1:-}"
    local subject="${2:-}"
    local description="${3:-}"

    if [[ -z "$list_name" ]] || [[ -z "$subject" ]]; then
        echo -e "${RED}Error: List name and subject required${NC}" >&2
        usage 1
    fi

    local tasks_file
    tasks_file=$(get_tasks_file "$list_name")

    if [[ ! -f "$tasks_file" ]]; then
        echo -e "${RED}Error: Task list '$list_name' not found. Run 'init' first.${NC}"
        exit 1
    fi

    # Get next task ID
    local next_id
    next_id=$(jq '.tasks | length + 1' "$tasks_file")

    # Add task to tasks.json (using temp file for atomic write)
    local temp_file
    temp_file=$(mktemp)
    jq --arg subject "$subject" \
       --arg desc "$description" \
       --argjson id "$next_id" \
       '.tasks += [{
         "id": $id,
         "subject": $subject,
         "description": $desc,
         "blocked_by": [],
         "blocks": []
       }]' "$tasks_file" > "$temp_file"
    mv "$temp_file" "$tasks_file"

    # Create initial status file
    local status_file
    status_file=$(get_status_file "$list_name" "$next_id")
    echo '{"status": "pending"}' > "$status_file"

    echo -e "${GREEN}Added task #$next_id: $subject${NC}"
}

cmd_block() {
    local list_name="${1:-}"
    local task_id="${2:-}"
    local blocked_by="${3:-}"

    if [[ -z "$list_name" ]] || [[ -z "$task_id" ]] || [[ -z "$blocked_by" ]]; then
        echo -e "${RED}Error: List name, task ID, and blocked-by ID required${NC}" >&2
        usage 1
    fi

    local tasks_file
    tasks_file=$(get_tasks_file "$list_name")

    # Update blocked_by array for task
    local temp_file
    temp_file=$(mktemp)
    jq --argjson id "$task_id" \
       --argjson blocked_by "$blocked_by" \
       '(.tasks[] | select(.id == $id).blocked_by) += [$blocked_by] |
        (.tasks[] | select(.id == $blocked_by).blocks) += [$id]' \
       "$tasks_file" > "$temp_file"
    mv "$temp_file" "$tasks_file"

    echo -e "${GREEN}Task #$task_id now blocked by #$blocked_by${NC}"
}

cmd_status() {
    local list_name="${1:-}"
    local task_id="${2:-}"
    local new_status="${3:-}"

    if [[ -z "$list_name" ]] || [[ -z "$task_id" ]] || [[ -z "$new_status" ]]; then
        echo -e "${RED}Error: List name, task ID, and status required${NC}" >&2
        usage 1
    fi

    # Validate status
    case "$new_status" in
        pending|in_progress|completed) ;;
        *)
            echo -e "${RED}Error: Invalid status. Use: pending, in_progress, completed${NC}"
            exit 1
            ;;
    esac

    local status_file
    status_file=$(get_status_file "$list_name" "$task_id")

    # Write status file (atomic via temp file)
    local temp_file
    temp_file=$(mktemp)

    if [[ "$new_status" == "completed" ]]; then
        cat > "$temp_file" << EOF
{"status": "completed", "completed_at": "$(date -Iseconds)"}
EOF
    elif [[ "$new_status" == "in_progress" ]]; then
        cat > "$temp_file" << EOF
{"status": "in_progress", "started_at": "$(date -Iseconds)"}
EOF
    else
        echo '{"status": "pending"}' > "$temp_file"
    fi

    mv "$temp_file" "$status_file"

    echo -e "${GREEN}Task #$task_id status: $new_status${NC}"
}

cmd_view() {
    local list_name="${1:-}"

    if [[ -z "$list_name" ]]; then
        echo -e "${RED}Error: List name required${NC}" >&2
        usage 1
    fi

    local tasks_file
    tasks_file=$(get_tasks_file "$list_name")
    local task_dir
    task_dir=$(get_task_dir "$list_name")

    if [[ ! -f "$tasks_file" ]]; then
        echo -e "${RED}Error: Task list '$list_name' not found${NC}"
        exit 1
    fi

    echo ""
    echo -e "${BLUE}## Task List: $list_name${NC}"
    echo ""

    local total=0
    local completed=0
    local in_progress=0
    local pending=0

    # Read tasks and their statuses
    while IFS= read -r task; do
        local id subject blocked_by blocks
        id=$(echo "$task" | jq -r '.id')
        subject=$(echo "$task" | jq -r '.subject')
        blocked_by=$(echo "$task" | jq -r '.blocked_by | join(", ")')
        blocks=$(echo "$task" | jq -r '.blocks | join(", ")')

        # Read status from status file
        local status_file status
        status_file=$(get_status_file "$list_name" "$id")
        if [[ -f "$status_file" ]]; then
            status=$(jq -r '.status' "$status_file")
        else
            status="pending"
        fi

        total=$((total + 1))

        # Format output based on status
        case "$status" in
            completed)
                echo -e "${GREEN}#$id [x] $subject${NC}"
                completed=$((completed + 1))
                ;;
            in_progress)
                echo -e "${CYAN}#$id [>] $subject${NC}"
                in_progress=$((in_progress + 1))
                ;;
            pending)
                if [[ -n "$blocked_by" ]]; then
                    echo -e "${YELLOW}#$id [ ] $subject${NC}"
                    echo -e "   ${YELLOW}└─ blocked by: #$blocked_by${NC}"
                else
                    echo -e "#$id [ ] $subject"
                fi
                pending=$((pending + 1))
                ;;
        esac

        if [[ -n "$blocks" ]]; then
            echo -e "   └─ blocks: #$blocks"
        fi

    done < <(jq -c '.tasks[]' "$tasks_file")

    echo ""
    echo -e "Total: $total | ${GREEN}Completed: $completed${NC} | ${CYAN}In Progress: $in_progress${NC} | Pending: $pending"
    echo ""
}

cmd_export() {
    local list_name="${1:-}"

    if [[ -z "$list_name" ]]; then
        echo -e "${RED}Error: List name required${NC}" >&2
        usage 1
    fi

    local tasks_file
    tasks_file=$(get_tasks_file "$list_name")
    local task_dir
    task_dir=$(get_task_dir "$list_name")
    local output_file="$task_dir/${list_name}-tasks.md"

    if [[ ! -f "$tasks_file" ]]; then
        echo -e "${RED}Error: Task list '$list_name' not found${NC}"
        exit 1
    fi

    # Generate markdown
    {
        echo "# Task List: $list_name"
        echo ""
        echo "**Generated:** $(date)"
        echo ""

        local total=0 completed=0

        # Count totals
        while IFS= read -r task; do
            local id
            id=$(echo "$task" | jq -r '.id')
            local status_file
            status_file=$(get_status_file "$list_name" "$id")
            local status="pending"
            [[ -f "$status_file" ]] && status=$(jq -r '.status' "$status_file")

            total=$((total + 1))
            [[ "$status" == "completed" ]] && completed=$((completed + 1))
        done < <(jq -c '.tasks[]' "$tasks_file")

        echo "## Summary"
        echo ""
        echo "- Total: $total"
        echo "- Completed: $completed"
        echo "- Remaining: $((total - completed))"
        echo ""
        echo "---"
        echo ""
        echo "## Tasks"
        echo ""

        # Output each task
        while IFS= read -r task; do
            local id subject description blocked_by
            id=$(echo "$task" | jq -r '.id')
            subject=$(echo "$task" | jq -r '.subject')
            description=$(echo "$task" | jq -r '.description')
            blocked_by=$(echo "$task" | jq -r '.blocked_by | map("#" + tostring) | join(", ")')

            local status_file status
            status_file=$(get_status_file "$list_name" "$id")
            status="pending"
            [[ -f "$status_file" ]] && status=$(jq -r '.status' "$status_file")

            local checkbox="[ ]"
            [[ "$status" == "completed" ]] && checkbox="[x]"
            [[ "$status" == "in_progress" ]] && checkbox="[>]"

            echo "### Task $id: $subject"
            echo ""
            echo "- **Status:** $checkbox $status"
            [[ -n "$blocked_by" ]] && echo "- **Blocked By:** $blocked_by"
            [[ -n "$description" ]] && echo -e "\n$description"
            echo ""
            echo "---"
            echo ""

        done < <(jq -c '.tasks[]' "$tasks_file")

    } > "$output_file"

    echo -e "${GREEN}Exported to: $output_file${NC}"
}

# =============================================================================
# Main
# =============================================================================

if [[ $# -lt 1 ]]; then
    usage 1
fi

COMMAND="$1"
shift

case "$COMMAND" in
    -h|--help|help)
        usage
        ;;
    init)
        cmd_init "$@"
        ;;
    add)
        cmd_add "$@"
        ;;
    block)
        cmd_block "$@"
        ;;
    status)
        cmd_status "$@"
        ;;
    view)
        cmd_view "$@"
        ;;
    export)
        cmd_export "$@"
        ;;
    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}" >&2
        usage 1
        ;;
esac
