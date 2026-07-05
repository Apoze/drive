import {
  buildMessagesWidgetInitCommand,
  getFeedbackItemDescriptors,
  shouldShowFeedbackButton,
} from "../feedbackRuntime";

describe("feedbackRuntime", () => {
  it("builds feedback item descriptors from config items", () => {
    expect(
      getFeedbackItemDescriptors({
        form: { url: "https://form.example.test" },
        tchap: { url: "https://tchap.example.test" },
      }),
    ).toEqual([
      {
        description: "feedback.modal.buttons.form.description",
        href: "https://form.example.test",
        kind: "form",
        title: "feedback.modal.buttons.form.title",
      },
      {
        description: "feedback.modal.buttons.tchap.description",
        href: "https://tchap.example.test",
        kind: "tchap",
        title: "feedback.modal.buttons.tchap.title",
      },
    ]);
  });

  it("hides feedback when the entrypoint itself is disabled", () => {
    expect(
      shouldShowFeedbackButton({
        idle: false,
        items: [],
        showButton: false,
      }),
    ).toBe(false);
  });

  it("keeps the button visible in idle mode even without href targets", () => {
    expect(
      shouldShowFeedbackButton({
        idle: true,
        items: [],
        showButton: true,
      }),
    ).toBe(true);
  });

  it("requires at least one href outside idle mode", () => {
    expect(
      shouldShowFeedbackButton({
        idle: false,
        items: [{ kind: "form", title: "a", description: "b" }],
        showButton: true,
      }),
    ).toBe(false);
  });

  it("builds the widget init command with optional email", () => {
    expect(
      buildMessagesWidgetInitCommand({
        apiUrl: "https://api.example.test",
        channel: "support",
        email: "jane@example.test",
        emailPlaceholder: "email-placeholder",
        placeholder: "placeholder",
        submitText: "submit",
        successText: "success",
        successText2: "success-2",
        title: "title",
      }),
    ).toEqual([
      "feedback",
      "init",
      {
        api: "https://api.example.test",
        channel: "support",
        email: "jane@example.test",
        emailPlaceholder: "email-placeholder",
        placeholder: "placeholder",
        submitText: "submit",
        successText: "success",
        successText2: "success-2",
        title: "title",
      },
    ]);
  });
});
