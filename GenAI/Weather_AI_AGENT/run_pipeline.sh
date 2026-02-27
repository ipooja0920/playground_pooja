#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# run_pipeline.sh — Weather AI Agent scheduled runner
#
# Runs main.py and retries automatically on RAI filter blocks or
# script validation failures. Each run is logged with a timestamped
# file under logs/.
#
# Scheduled via cron at 8:00 am, 6:00 pm, and 9:00 pm EST daily.
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="/Users/pokeapokemon/playground_pooja/GenAI/Weather_AI_AGENT"
PYTHON="/opt/anaconda3/bin/python"
LOG_DIR="$SCRIPT_DIR/logs"
MAX_RETRIES=5        # max full pipeline retries per scheduled run
RETRY_DELAY=300      # seconds to wait between retries (5 min)

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/pipeline_$(date +%Y%m%d_%H%M%S).log"

echo "================================================================" | tee -a "$LOG_FILE"
echo "  Weather AI Agent — pipeline started at $(date)"               | tee -a "$LOG_FILE"
echo "================================================================" | tee -a "$LOG_FILE"

cd "$SCRIPT_DIR" || { echo "ERROR: Could not cd to $SCRIPT_DIR" | tee -a "$LOG_FILE"; exit 1; }

for attempt in $(seq 1 $MAX_RETRIES); do
    echo "" | tee -a "$LOG_FILE"
    echo "--- Attempt $attempt / $MAX_RETRIES  [$(date +%H:%M:%S)] ---" | tee -a "$LOG_FILE"

    output=$("$PYTHON" main.py 2>&1)
    echo "$output" | tee -a "$LOG_FILE"

    # ── Success ───────────────────────────────────────────────────────────────
    if echo "$output" | grep -q "Final video saved"; then
        echo "" | tee -a "$LOG_FILE"
        echo "SUCCESS: final_video.mp4 saved on attempt $attempt." | tee -a "$LOG_FILE"
        exit 0
    fi

    # ── Decide retry reason ───────────────────────────────────────────────────
    if echo "$output" | grep -q "rai_media_filtered"; then
        REASON="RAI filter blocked all Veo attempts"
    elif echo "$output" | grep -q "Tests Failed"; then
        REASON="Script or prompt validation failed"
    elif echo "$output" | grep -q "Failed to fetch weather"; then
        REASON="Weather fetch failed (wttr.in / NWS network error)"
    else
        REASON="Unknown failure"
    fi

    if [ $attempt -lt $MAX_RETRIES ]; then
        echo "RETRY: $REASON — waiting ${RETRY_DELAY}s before attempt $((attempt + 1))..." | tee -a "$LOG_FILE"
        sleep $RETRY_DELAY
    fi
done

echo "" | tee -a "$LOG_FILE"
echo "FAILED: Pipeline did not complete after $MAX_RETRIES attempts." | tee -a "$LOG_FILE"
exit 1
