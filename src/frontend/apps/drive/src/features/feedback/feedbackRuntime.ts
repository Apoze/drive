export type FeedbackItemDescriptor = {
  kind: string;
  title: string;
  description: string;
  href?: string;
};

export const getFeedbackItemDescriptors = (
  items?: Record<string, { url: string }>,
): FeedbackItemDescriptor[] => {
  return items
    ? Object.entries(items).map(([key, value]) => ({
        description: `feedback.modal.buttons.${key}.description`,
        href: value.url,
        kind: key,
        title: `feedback.modal.buttons.${key}.title`,
      }))
    : [];
};

export const shouldShowFeedbackButton = ({
  idle,
  items,
  showButton,
}: {
  idle?: boolean;
  items: FeedbackItemDescriptor[];
  showButton?: boolean;
}) => {
  if (!showButton) {
    return false;
  }

  if (!idle && items.filter((button) => !!button.href).length === 0) {
    return false;
  }

  return true;
};

export const buildMessagesWidgetInitCommand = ({
  apiUrl,
  channel,
  email,
  emailPlaceholder,
  placeholder,
  submitText,
  successText,
  successText2,
  title,
}: {
  apiUrl: string;
  channel: string;
  email?: string;
  emailPlaceholder: string;
  placeholder: string;
  submitText: string;
  successText: string;
  successText2: string;
  title: string;
}) => {
  return [
    "feedback",
    "init",
    {
      api: apiUrl,
      channel,
      email,
      emailPlaceholder,
      placeholder,
      submitText,
      successText,
      successText2,
      title,
    },
  ] as const;
};
