import type { LandingContent } from './types'

const installHref = '/getting-started/installation'
const installGuide = { text: 'installation guide', href: installHref }

export const en: LandingContent = {
  eyebrow: 'Background transcription daemon for macOS',
  titleLines: [['Drop audio into a folder.'], ['Get a transcript in your notes.']],
  lede: [
    'transcribe-inbox watches ',
    { code: '~/Transcribe/inbox' },
    '. When a new recording arrives, it transcribes it on the Apple Silicon GPU and saves the transcript as plain files in your Obsidian vault or any other folder.',
  ],
  getStarted: 'Get started',
  installHref,
  platformNote: ['This is the first command. The ', installGuide, ' has the rest.'],
  copy: { idle: 'Copy', done: 'Copied', failed: 'Copy failed', label: 'Copy command' },

  demo: {
    label: 'Example',
    ariaLabel:
      'Example: week2.m4a copied into the lectures inbox becomes transcript.md and three other files in the notes folder.',
    running: 'transcribing on the Apple Silicon GPU',
    complete: 'Done. 4 files saved.',
    caption: 'Example output. The transcription language is currently fixed to Korean.',
  },

  values: {
    title: 'What it does',
    intro: 'You copy a recording into one folder and the transcript appears in another. There is no app window to keep open.',
    items: [
      {
        title: 'Runs locally',
        body: ['whisper.cpp or whispermlx transcribes on the Apple Silicon GPU. The daemon makes no cloud API calls.'],
      },
      {
        title: 'The folder path is the config',
        body: [
          'Where you put a file decides how it is handled: ',
          { code: 'inbox/<category>/[mode]/file' },
          '. The first folder is the category, for example ',
          { code: 'lectures' },
          ' or ',
          { code: 'meetings' },
          '.',
        ],
      },
      {
        title: 'Plain files as output',
        body: [
          'Each recording produces ',
          { code: 'transcript.json' },
          ', ',
          { code: '.md' },
          ', ',
          { code: '.txt' },
          ' and ',
          { code: '.srt' },
          '. The output folder can be an Obsidian vault or any other folder.',
        ],
      },
      {
        title: 'No summary',
        body: ['The transcript is saved as recognized, with timestamps. Summarizing is left to you.'],
      },
    ],
  },

  flow: {
    title: 'How it works',
    intro: 'The daemon runs under launchd and handles one job at a time. Job state is kept in a database, so work resumes after a restart.',
    steps: [
      { title: 'Drop', body: 'Copy an audio or video file into a category folder.', path: 'inbox/lectures/week2.m4a' },
      {
        title: 'Detect',
        body: 'Once the file stops growing, the daemon queues it. Jobs are keyed by content hash, so the same file is not queued twice.',
      },
      { title: 'Transcribe', body: 'whisper.cpp or whispermlx, depending on the mode, transcribes the file on the Apple Silicon GPU.' },
      {
        title: 'Publish',
        body: 'The four transcript files are saved to your notes folder, the original moves to the archive, and a macOS notification appears.',
        path: 'Transcripts/lectures/week2/',
      },
    ],
    modesLabel: 'Modes',
    modes: [
      { name: 'asr', description: 'One speaker. Used when there is no mode folder.' },
      { name: 'diarize', description: 'Several speakers mixed in one file. Runs on whispermlx.' },
      { name: 'asr-multitrack', description: 'One file per speaker, placed together in a session folder.' },
    ],
  },

  quickStart: {
    title: 'Quick start',
    intro: 'Installation has four steps. The commands here cover the first one.',
    steps: [
      { title: 'Install the tools', body: ['Install ffmpeg and whisper.cpp with Homebrew, clone the repository and run ', { code: 'uv sync' }, '.'] },
      { title: 'Set up the database', body: ['Create the database and apply the schema. Job state is stored there.'] },
      { title: 'Fill in the plist', body: ['Copy the plist template and set the paths for the inbox, the notes folder and the archive.'] },
      { title: 'Load the daemon', body: ['Copy the plist to ', { code: '~/Library/LaunchAgents' }, ' and run ', { code: 'launchctl load' }, '.'] },
    ],
    commandsLabel: 'Step 1 commands',
    next: ['Steps 2 to 4 are in the ', installGuide, '.'],
  },

  privacy: {
    title: 'Privacy',
    statement: 'transcribe-inbox does not send your recordings or transcripts anywhere.',
    facts: [
      'No cloud API calls. The model runs on your Mac.',
      'Originals move to a local archive folder.',
      'Transcripts are plain files in a folder you choose.',
      'Open source under the MIT license.',
    ],
  },

  closing: {
    title: 'Install',
    note: ['Runs on macOS with Apple Silicon only. Continue with the ', installGuide, '.'],
  },

  footer: { license: 'MIT License', languagesLabel: 'Languages' },
}
