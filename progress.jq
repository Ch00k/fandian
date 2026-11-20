# Cuts Claude's stream-json events, one per input line (jq -R), down to the readable log a run
# shows, each line stamped with the time since $start: the model and MCP servers the session starts
# with, the agent's text, each tool call (a Bash call by its description, a write to the
# repository's issues by its gh command), each failed tool result and the final status. $color
# paints it with ANSI codes.

def paint($code): if $color then "\u001b[\($code)m\(.)\u001b[0m" else . end;
def one_line: gsub("\\s+"; " ") | .[0:200];
def two_digits: tostring | if length < 2 then "0" + . else . end;
def stamp: (now - $start | floor) as $s
  | "\($s / 3600 | floor):\($s / 60 | floor % 60 | two_digits):\($s % 60 | two_digits)" | paint("2");
def line: "\(stamp) \(.)";

fromjson?
| if .type == "system" and .subtype == "init" then
    (.mcp_servers // []) as $servers
    | (if all($servers[]; .status == "connected") then "32" else "1;31" end) as $mcp
    | "model \(.model), MCP \($servers | map("\(.name) \(.status)") | join(", ") | paint($mcp))"
    | line
  elif .type == "assistant" then
    .message.content[]
    | if .type == "text" then
        "\n" + (.text | split("\n") | map(paint("1") | line) | join("\n"))
      elif .type == "tool_use" and .name == "Bash"
           and (.input.command | test("gh issue (create|edit|reopen|close|comment)")) then
        "  \("issues" | paint("1;33")) \(.input.command | gsub("\\s+"; " ") | sub("^.*?gh issue"; "gh issue")
                                          | one_line | paint("33"))" | line
      elif .type == "tool_use" then
        "  \(.name | sub("^mcp__[^_]+__"; "") | paint("36")) \(.input
            | .description // .command // .url // .file_path // .element // .pattern // .query // tostring
            | one_line | paint("2"))" | line
      else empty end
  elif .type == "user" then
    .message.content[]? | select(.type? == "tool_result" and .is_error)
    | "  \(.content | if type == "array" then map(.text? // empty) | join(" ") else . end
               | "! " + one_line | paint("31"))" | line
  elif .type == "result" then
    (if .subtype == "success" and (.is_error | not) then "1;32" else "1;31" end) as $code
    | "\n" + ("--- \(.subtype): \(.num_turns) turns in \(.duration_ms / 60000 | floor) min" | paint($code) | line)
  else empty end
