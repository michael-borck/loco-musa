import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { loco } from '@locolabo/theme';

export default defineConfig({
  site: 'https://locomusa.org',
  integrations: [
    starlight(
      loco({
        project: 'loco-musa',
        title: 'LocoMusa',
        description: 'A thinking-partner benchmark for local LLMs: ideation, reframing, and dialogue, scored pairwise against frontier anchors.',
        home: 'https://locomusa.org',
        github: 'loco-musa',
        accent: { low: '#1b1433', main: '#7c5cff', high: '#d6ccff' },
        sidebar: [
          {
            label: 'Benchmark',
            items: [
              { label: 'Overview', link: '/' },
              { label: 'Methodology', slug: 'methodology' },
              { label: 'Human judging', slug: 'human-judging' },
              { label: 'Authoring tasks', slug: 'authoring' },
            ],
          },
        ],
      })
    ),
  ],
});
