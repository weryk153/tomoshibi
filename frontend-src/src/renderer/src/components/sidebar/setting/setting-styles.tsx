const isElectron = window.api !== undefined;
export const settingStyles = {
  settingUI: {
    tabs: {
      root: {
        width: '100%',
        variant: 'plain' as const,
        colorPalette: 'gray',
      },
      content: {},
      trigger: {
        color: 'whiteAlpha.600',
        _selected: {
          color: 'white',
        },
        _hover: {
          color: 'white',
        },
      },
      list: {
        display: 'flex',
        flexWrap: 'wrap' as const,
        rowGap: 1,
        justifyContent: 'flex-start',
        width: '100%',
        borderBottom: '1px solid',
        borderColor: 'whiteAlpha.200',
        mb: 4,
        pl: 0,
      },
    },
    drawerContent: {
      bg: 'gray.900',
      maxWidth: '440px',
      height: isElectron ? 'calc(100vh - 30px)' : '100vh',
      borderLeft: '1px solid',
      borderColor: 'whiteAlpha.200',
    },
    drawerHeader: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      width: '100%',
      position: 'relative',
      px: 6,
      py: 4,
    },
    drawerTitle: {
      color: 'white',
      fontSize: 'lg',
      fontWeight: 'semibold',
    },
    closeButton: {
      position: 'absolute',
      right: 1,
      top: 1,
      color: 'white',

    },
    // The drawer is gray.900, but Chakra's `outline` variant inherits the
    // default foreground colour, which is near-black — the footer button was
    // legible only by its border. Every other control in this file states its
    // colour explicitly for the same reason.
    footerButton: {
      color: 'white',
      borderColor: 'whiteAlpha.400',
      _hover: {
        bg: 'whiteAlpha.200',
        borderColor: 'whiteAlpha.600',
      },
    },
  },
  general: {
    container: {
      align: 'stretch',
      gap: 6,
      p: 4,
    },
    field: {
      label: {
        color: 'whiteAlpha.800',
      },
    },
    select: {
      root: {
        colorPalette: 'gray',
        bg: 'gray.800',
      },
      trigger: {
        bg: 'gray.800',
      },
    },
    input: {
      bg: 'gray.800',
    },
    fieldLabel: {
      fontSize: '14px',
      color: 'gray.600',
    },
  },
  common: {
    field: {
      orientation: 'horizontal' as const,
    },
    fieldLabel: {
      fontSize: 'sm',
      color: 'whiteAlpha.800',
      whiteSpace: 'nowrap' as const,
    },
    switch: {
      size: 'md' as const,
      colorPalette: 'blue' as const,
      variant: 'solid' as const,
    },
    numberInput: {
      root: {
        pattern: '[0-9]*\\.?[0-9]*',
        inputMode: 'decimal' as const,
      },
      input: {
        bg: 'whiteAlpha.100',
        borderColor: 'whiteAlpha.200',
        _hover: {
          bg: 'whiteAlpha.200',
        },
      },
    },
    container: {
      gap: 8,
      maxW: 'sm',
      css: { '--field-label-width': '120px' },
    },
    input: {
      bg: 'whiteAlpha.100',
      borderColor: 'whiteAlpha.200',
      _hover: {
        bg: 'whiteAlpha.200',
      },
    },
  },
  live2d: {
    emotionMap: {
      title: {
        fontWeight: 'bold',
        mb: 4,
      },
      entry: {
        mb: 2,
      },
      button: {
        colorPalette: 'blue',
        mt: 2,
      },
      deleteButton: {
        colorPalette: 'red',
      },
    },
  },
};
