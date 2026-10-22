// Generated from the engine registry for tests; regenerate when a template changes.
export const SCHEMAS = {
  capacity_fit: {
    additionalProperties: false,
    properties: {
      headcount_from: {
        default: "group_sizes",
        enum: ["group_sizes", "activity_attr"],
        title: "Headcount from",
        type: "string",
      },
      headcount_attr: {
        anyOf: [
          {
            pattern: "^[a-z][a-z0-9_]{0,62}$",
            type: "string",
          },
          {
            type: "null",
          },
        ],
        default: null,
        description: "Activity attribute holding the headcount",
        title: "Headcount attribute",
      },
    },
    title: "Params",
    type: "object",
  },
  max_load: {
    additionalProperties: false,
    properties: {
      period: {
        enum: ["day", "week", "horizon"],
        title: "Period",
        type: "string",
      },
      window: {
        anyOf: [
          {
            pattern: "^[a-z][a-z0-9_]{0,62}$",
            type: "string",
            "x-ref": "window",
          },
          {
            type: "null",
          },
        ],
        default: null,
        description: "Only count activities in this part of the day",
        title: "Part of day",
      },
      max_count: {
        anyOf: [
          {
            minimum: 0,
            type: "integer",
          },
          {
            type: "null",
          },
        ],
        default: null,
        title: "Max activities",
      },
      max_minutes: {
        anyOf: [
          {
            minimum: 0,
            type: "integer",
          },
          {
            type: "null",
          },
        ],
        default: null,
        title: "Max time",
        "x-unit": "minutes",
      },
    },
    required: ["period"],
    title: "Params",
    type: "object",
  },
  min_load: {
    additionalProperties: false,
    properties: {
      period: {
        enum: ["day", "week", "horizon"],
        title: "Period",
        type: "string",
      },
      window: {
        anyOf: [
          {
            pattern: "^[a-z][a-z0-9_]{0,62}$",
            type: "string",
            "x-ref": "window",
          },
          {
            type: "null",
          },
        ],
        default: null,
        description: "Only count activities in this part of the day",
        title: "Part of day",
      },
      min_count: {
        anyOf: [
          {
            minimum: 0,
            type: "integer",
          },
          {
            type: "null",
          },
        ],
        default: null,
        title: "Min activities",
      },
      min_minutes: {
        anyOf: [
          {
            minimum: 0,
            type: "integer",
          },
          {
            type: "null",
          },
        ],
        default: null,
        title: "Min time",
        "x-unit": "minutes",
      },
    },
    required: ["period"],
    title: "Params",
    type: "object",
  },
  min_rest: {
    additionalProperties: false,
    properties: {
      minutes: {
        exclusiveMinimum: 0,
        title: "Rest",
        type: "integer",
        "x-unit": "minutes",
      },
    },
    required: ["minutes"],
    title: "Params",
    type: "object",
  },
  max_consecutive: {
    $defs: {
      ActivityFilter: {
        additionalProperties: false,
        properties: {
          series_ids: {
            default: [],
            items: {
              maxLength: 100,
              minLength: 1,
              type: "string",
              "x-ref": "series",
            },
            title: "Demands",
            type: "array",
          },
          attrs: {
            default: [],
            items: {
              $ref: "#/$defs/AttributePredicate",
            },
            title: "Conditions",
            type: "array",
          },
        },
        title: "ActivityFilter",
        type: "object",
      },
      AttributePredicate: {
        additionalProperties: false,
        properties: {
          attr: {
            pattern: "^[a-z][a-z0-9_]{0,62}$",
            title: "Attr",
            type: "string",
          },
          op: {
            enum: ["eq", "ne", "in", "gte", "lte", "contains"],
            title: "Op",
            type: "string",
          },
          value: {
            anyOf: [
              {
                type: "string",
              },
              {
                type: "integer",
              },
              {
                type: "number",
              },
              {
                type: "boolean",
              },
              {
                items: {
                  anyOf: [
                    {
                      type: "string",
                    },
                    {
                      type: "integer",
                    },
                    {
                      type: "number",
                    },
                    {
                      type: "boolean",
                    },
                  ],
                },
                type: "array",
              },
            ],
            title: "Value",
          },
        },
        required: ["attr", "op", "value"],
        title: "AttributePredicate",
        type: "object",
      },
    },
    additionalProperties: false,
    properties: {
      unit: {
        const: "days",
        title: "Counted in",
        type: "string",
      },
      max: {
        exclusiveMinimum: 0,
        title: "Max in a row",
        type: "integer",
      },
      activity_filter: {
        anyOf: [
          {
            $ref: "#/$defs/ActivityFilter",
          },
          {
            type: "null",
          },
        ],
        default: null,
        title: "Only count",
      },
    },
    required: ["unit", "max"],
    title: "Params",
    type: "object",
  },
  spread: {
    additionalProperties: false,
    properties: {
      max_per_day: {
        anyOf: [
          {
            exclusiveMinimum: 0,
            type: "integer",
          },
          {
            type: "null",
          },
        ],
        default: null,
        title: "Max per day",
      },
      min_days_apart: {
        anyOf: [
          {
            exclusiveMinimum: 0,
            type: "integer",
          },
          {
            type: "null",
          },
        ],
        default: null,
        title: "Min days apart",
      },
    },
    title: "Params",
    type: "object",
  },
  same_time: {
    additionalProperties: false,
    properties: {
      link_groups: {
        items: {
          items: {
            maxLength: 100,
            minLength: 1,
            type: "string",
            "x-ref": "series",
          },
          type: "array",
        },
        minItems: 1,
        title: "Linked demands",
        type: "array",
      },
    },
    required: ["link_groups"],
    title: "Params",
    type: "object",
  },
  precedence: {
    $defs: {
      Pair: {
        additionalProperties: false,
        properties: {
          before: {
            maxLength: 100,
            minLength: 1,
            title: "Before",
            type: "string",
            "x-ref": "series",
          },
          after: {
            maxLength: 100,
            minLength: 1,
            title: "After",
            type: "string",
            "x-ref": "series",
          },
        },
        required: ["before", "after"],
        title: "Pair",
        type: "object",
      },
    },
    additionalProperties: false,
    properties: {
      pairs: {
        items: {
          $ref: "#/$defs/Pair",
        },
        minItems: 1,
        title: "Pairs",
        type: "array",
      },
      min_gap: {
        default: 0,
        minimum: 0,
        title: "Min gap",
        type: "integer",
        "x-unit": "minutes",
      },
    },
    required: ["pairs"],
    title: "Params",
    type: "object",
  },
  preference: {
    $defs: {
      Pair: {
        additionalProperties: false,
        properties: {
          resource_id: {
            maxLength: 100,
            minLength: 1,
            title: "Resource",
            type: "string",
            "x-ref": "resource",
          },
          series_id: {
            maxLength: 100,
            minLength: 1,
            title: "Demand",
            type: "string",
            "x-ref": "series",
          },
          mode: {
            enum: ["prefer", "avoid"],
            title: "Mode",
            type: "string",
          },
        },
        required: ["resource_id", "series_id", "mode"],
        title: "Pair",
        type: "object",
      },
    },
    additionalProperties: false,
    properties: {
      source: {
        description: "Use availability calendars or the pairs below",
        enum: ["calendar", "explicit"],
        title: "Source",
        type: "string",
      },
      pairs: {
        default: [],
        items: {
          $ref: "#/$defs/Pair",
        },
        title: "Pairs",
        type: "array",
      },
    },
    required: ["source"],
    title: "Params",
    type: "object",
  },
  minimize_gaps: {
    additionalProperties: false,
    properties: {
      per_minutes: {
        description: "One penalty unit per this many idle minutes",
        exclusiveMinimum: 0,
        title: "Penalty every",
        type: "integer",
        "x-unit": "minutes",
      },
    },
    required: ["per_minutes"],
    title: "Params",
    type: "object",
  },
  balance: {
    additionalProperties: false,
    properties: {
      measure: {
        enum: ["count", "minutes"],
        title: "Measure",
        type: "string",
      },
    },
    required: ["measure"],
    title: "Params",
    type: "object",
  },
  fairness: {
    $defs: {
      ActivityFilter: {
        additionalProperties: false,
        properties: {
          series_ids: {
            default: [],
            items: {
              maxLength: 100,
              minLength: 1,
              type: "string",
              "x-ref": "series",
            },
            title: "Demands",
            type: "array",
          },
          attrs: {
            default: [],
            items: {
              $ref: "#/$defs/AttributePredicate",
            },
            title: "Conditions",
            type: "array",
          },
        },
        title: "ActivityFilter",
        type: "object",
      },
      AttributePredicate: {
        additionalProperties: false,
        properties: {
          attr: {
            pattern: "^[a-z][a-z0-9_]{0,62}$",
            title: "Attr",
            type: "string",
          },
          op: {
            enum: ["eq", "ne", "in", "gte", "lte", "contains"],
            title: "Op",
            type: "string",
          },
          value: {
            anyOf: [
              {
                type: "string",
              },
              {
                type: "integer",
              },
              {
                type: "number",
              },
              {
                type: "boolean",
              },
              {
                items: {
                  anyOf: [
                    {
                      type: "string",
                    },
                    {
                      type: "integer",
                    },
                    {
                      type: "number",
                    },
                    {
                      type: "boolean",
                    },
                  ],
                },
                type: "array",
              },
            ],
            title: "Value",
          },
        },
        required: ["attr", "op", "value"],
        title: "AttributePredicate",
        type: "object",
      },
    },
    additionalProperties: false,
    properties: {
      counter: {
        pattern: "^[a-z][a-z0-9_]{0,62}$",
        title: "Ledger counter",
        type: "string",
      },
      activity_filter: {
        $ref: "#/$defs/ActivityFilter",
        title: "Counts activities",
      },
      lookback_days: {
        minimum: 0,
        title: "Look back (days)",
        type: "integer",
      },
    },
    required: ["counter", "activity_filter", "lookback_days"],
    title: "Params",
    type: "object",
  },
  day_distribution: {
    additionalProperties: false,
    properties: {},
    title: "Params",
    type: "object",
  },
  stability: {
    additionalProperties: false,
    properties: {
      per_change: {
        minimum: 0,
        title: "Penalty per moved activity",
        type: "integer",
      },
      per_resource_change: {
        minimum: 0,
        title: "Penalty per replaced resource",
        type: "integer",
      },
    },
    required: ["per_change", "per_resource_change"],
    title: "Params",
    type: "object",
  },
} as const;
