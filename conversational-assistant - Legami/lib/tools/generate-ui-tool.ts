import { components } from '@/config/components-definition'

const componentsList = components.map(component => {
  return { $ref: `#/$defs/${component.name}` }
})

const componentsDefinitions = components.reduce((acc, component: any) => {
  acc[component.name] = {
    type: 'object',
    properties: {
      name: {
        type: 'string',
        enum: [component.name]
      },
      ...component.parameters
    },
    // Strict schema requires all properties to be listed in required
    required: ['name', ...Object.keys(component.parameters)],
    additionalProperties: false
  }
  return acc
}, {} as { [key: string]: any })

export const generateUITool = {
  name: 'generate_ui',
  description:
    'Generate UI components dynamically to display relevant information.',
  parameters: {
    type: 'object',
    properties: {
      component: {
        anyOf: componentsList
      }
    },
    required: ['component'],
    additionalProperties: false,
    $defs: {
      component: {
        anyOf: componentsList
      },
      ...componentsDefinitions
    }
  },
  strict: true
}
