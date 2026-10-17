// Keep shared links to the earlier combined guides useful after splitting them.
export const legacyRoutes = {
  'building-agents': {
    default: '/tools',
    '#choose-the-model': '/models',
    '#intents-outcomes-and-templates': '/outcomes#fill-templates-from-tool-results',
    '#add-cancellation-to-the-order-agent': '/order-agent#add-the-cancellation-tool',
    '#define-tools': '/tools#define-a-tool',
    '#describe-parameters': '/parameters#configuration',
    '#common-mistakes': '/tools#behavior-and-limitations',
  },
  'tools-and-parameters': {
    default: '/tools',
    '#define-tools': '/tools#define-a-tool',
    '#describe-parameters': '/parameters#configuration',
    '#add-cancellation-to-the-order-agent': '/order-agent#add-the-cancellation-tool',
    '#common-mistakes': '/tools#behavior-and-limitations',
  },
  'intents-and-outcomes': {
    default: '/intents',
    '#imports': '/intents#configuration',
    '#define-an-intent': '/intents#a-greeting-without-tools',
    '#define-outcomes': '/outcomes#define-an-outcome',
    '#templates-and-returned-values': '/outcomes#fill-templates-from-tool-results',
    '#register-the-configuration': '/intents#using-intents-in-an-agent',
    '#extend-an-intent-with-another-action': '/order-agent#extend-the-quickstart-with-cancellation',
    '#limits-and-common-mistakes': '/intents#configuration',
  },
  'memory-and-approval': {
    default: '/middleware-and-approval',
    '#custom-middleware': '/middleware-and-approval#define-middleware',
    '#memory-chooses-what-the-model-sees': '/memory-and-checkpoints#memory-chooses-what-the-model-sees',
    '#sqlite-stores-the-conversation': '/memory-and-checkpoints#sqlite-stores-the-conversation',
    '#history-reset-and-shutdown': '/memory-and-checkpoints#history-reset-and-shutdown',
  },
  examples: {
    default: '/order-agent',
    '#order-support-agent': '/order-agent',
    '#flight-desk-agent': '/flight-desk-agent',
  },
};
