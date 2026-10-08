export type Language = "zak" | "python";
export type DemoTask = {
    id: string;
    title: string;
    category: string;
    description: string;
    signature: string;
    examples: { input: string; output: string }[];
    zak: string;
    python: string;
    promptTokens: number;
    completionTokens: Record<Language, number>;
};

// Public task statements and illustrative solutions only. Hidden tests stay on the server.
export const tasks: DemoTask[] = [
    {
        id: "array_sum",
        title: "Array sum",
        category: "Arrays",
        description:
            "Given an array of integers, return the sum of all integers in the array. Your solution should handle an empty array and negative numbers.",
        signature: "solve(nums: integer[]) → integer",
        examples: [
            { input: "[1, 2, 3, 4, 5]", output: "15" },
            { input: "[]", output: "0" },
        ],
        zak: "@solve(nums:[I])I{\n  total:=0;\n  ~n:nums{\n    total+=n\n  }\n  ^total\n}",
        python: "def solve(nums: list[int]) -> int:\n    total = 0\n    for n in nums:\n        total += n\n    return total",
        promptTokens: 1146,
        completionTokens: { zak: 36, python: 53 },
    },
    {
        id: "palindrome",
        title: "Palindrome",
        category: "Strings",
        description:
            "Given a string, return true if the string reads the same forward and backward. Otherwise return false. Compare characters exactly as provided.",
        signature: "solve(text: string) → boolean",
        examples: [
            { input: '"racecar"', output: "true" },
            { input: '"zak"', output: "false" },
        ],
        zak: "@solve(text:S)B{\n  ^text==rev(text)\n}",
        python: "def solve(text: str) -> bool:\n    return text == text[::-1]",
        promptTokens: 1134,
        completionTokens: { zak: 18, python: 25 },
    },
    {
        id: "frequency_count",
        title: "Frequency count",
        category: "Maps",
        description:
            "Given an array of strings, return a map containing the number of times each string appears. An empty array should return an empty map.",
        signature: "solve(items: string[]) → map<string, integer>",
        examples: [
            { input: '["zak", "py", "zak"]', output: '{"zak": 2, "py": 1}' },
            { input: "[]", output: "{}" },
        ],
        zak: "@solve(items:[S]){S:I}{\n  counts:{S:I}={};\n  ~item:items{\n    ?item@counts{\n      counts[item]+=1\n    }:{\n      counts[item]=1\n    }\n  }\n  ^counts\n}",
        python: "def solve(items: list[str]) -> dict[str, int]:\n    counts: dict[str, int] = {}\n    for item in items:\n        if item in counts:\n            counts[item] += 1\n        else:\n            counts[item] = 1\n    return counts",
        promptTokens: 1162,
        completionTokens: { zak: 69, python: 94 },
    },
];

export const model = "Llama 3.1 8B Instruct";

export type DemoRun = {
    id: string;
    taskId: string;
    language: Language;
    source: string;
    python: string;
    seed: number;
    model: string;
    passed: boolean;
    promptTokens: number;
    completionTokens: number;
    createdAt: string;
};

export const sampleRuns: DemoRun[] = tasks.flatMap((task, i) =>
    (["zak", "python"] as const).map((language) => ({
        id: `sample-${task.id}-${language}`,
        taskId: task.id,
        language,
        source: task[language],
        python: task.python,
        seed: 42,
        model,
        passed: true,
        promptTokens: language === "zak" ? task.promptTokens : 212 + i * 18,
        completionTokens: task.completionTokens[language],
        createdAt: "2026-10-08T13:00:00Z",
    })),
);

export function matchesReference(
    source: string,
    task: DemoTask,
    language: Language,
) {
    const normalize = (value: string) =>
        language === "python"
            ? value.replace(/\r\n/g, "\n").trimEnd()
            : (
                  value.match(
                      /"(?:\\.|[^"\\])*"|[a-z_][a-z0-9_]*|\d+(?:\.\d+)?|:=|\+=|-=|\*=|\/=|%=|<<|==|!=|<=|>=|\.\.|[^\s]/g,
                  ) ?? []
              ).join("\u001f");
    return normalize(source) === normalize(task[language]);
}
