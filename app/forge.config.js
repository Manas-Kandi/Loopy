module.exports = {
  packagerConfig: {
    name: 'Loopy',
    executableName: 'Loopy',
    appBundleId: 'com.manaskandi.loopy',
    asar: false,
    ignore: [
      /^\/dist($|\/)/,
      /^\/out($|\/)/,
      /^\/scripts($|\/)/,
      /^\/\.pyinstaller($|\/)/,
      /^\/\.venv($|\/)/,
    ],
    osxSign: process.env.APPLE_IDENTITY ? {} : undefined,
    osxNotarize: process.env.APPLE_ID && process.env.APPLE_PASSWORD && process.env.APPLE_TEAM_ID
      ? {
          tool: 'notarytool',
          appleId: process.env.APPLE_ID,
          appleIdPassword: process.env.APPLE_PASSWORD,
          teamId: process.env.APPLE_TEAM_ID,
        }
      : undefined,
  },
  rebuildConfig: {},
  makers: [
    {
      name: '@electron-forge/maker-zip',
      platforms: ['darwin'],
    },
    {
      name: '@electron-forge/maker-dmg',
      platforms: ['darwin'],
      config: {
        overwrite: true,
      },
    },
  ],
  publishers: [
    {
      name: '@electron-forge/publisher-github',
      config: {
        repository: {
          owner: 'Manas-Kandi',
          name: '9xf-loops',
        },
        draft: true,
        prerelease: false,
      },
    },
  ],
};
