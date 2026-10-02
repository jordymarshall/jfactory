# Write simply: ASD-STE100

Owners read agent explanations between other work. Every explanation, report, PR description and document for people uses the writing rules of [ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/). STE100 is a controlled language for technical text: one word has one meaning, and sentences are short and direct. We follow its writing rules. We do not claim conformance to its full dictionary.

This applies to messages to the owner, handoff reports, PR descriptions and walkthroughs, setup records, runbooks and other documents people read. It does not replace the product's own copy rules for text inside the app. Where a project's standards map names rules for user-facing copy, those apply to the app.

## The rules

1. **Short sentences.** At most 20 words in an instruction, at most 25 words in a description. Split a longer sentence.
2. **One instruction per sentence.** Put steps in a numbered list, in the order the reader does them.
3. **Short paragraphs.** At most 6 sentences. Start with the most important point.
4. **Active voice.** Name who does the action: "CI runs the tests", not "the tests are run".
5. **Simple verb forms.** Use the present, simple past or simple future tense. Write instructions as commands: "Set the variable", not "You should set the variable".
6. **Common words with one meaning.** Use "use", not "utilize"; "start", not "initiate". Use the same word for the same thing every time. Do not switch between "runner", "machine" and "box" for one thing.
7. **Explain technical words.** Use a technical name when it is the right name, and explain it once in plain words the first time: "a migration (a change to the database structure)". Do not use internal names, abbreviations or tool jargon the reader does not know.
8. **Keep the small words.** Do not drop "the", "a" or "is" to make text shorter. Telegraphic text is harder to read.
9. **Be specific.** Give the number, the name or the link: "5 checks", not "a few checks"; "PR #188", not "the PR".
10. **Lists and tables for structure.** Use a list for steps or options and a table to compare things. Do not hide steps inside a long paragraph.
11. **Warnings first.** Start a warning or caution with the action or the risk: "Do not merge this before the release. The staging site will show errors."

## Check before you send

- Can the owner understand it without knowing the code or the tools?
- Does every sentence have one clear point, and is every term explained?
- Does the first sentence say the result or the decision needed?

If a sentence fails, rewrite it. Shorter is not always simpler: add the word that makes the meaning clear.
