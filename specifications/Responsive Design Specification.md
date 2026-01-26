# Responsive Design Specification

This document describes the responsive design implementation for massalia.events, ensuring the application works correctly across mobile, tablet, and desktop viewports.

## Breakpoints

The application uses Tailwind CSS standard breakpoints:

| Breakpoint | Prefix | Min Width | Target Devices |
|------------|--------|-----------|----------------|
| Base       | -      | 0px       | Mobile (small) |
| sm         | `sm:`  | 640px     | Mobile (large), Tablet portrait |
| md         | `md:`  | 853px*    | Tablet landscape |
| lg         | `lg:`  | 1024px    | Desktop |
| xl         | `xl:`  | 1280px    | Large desktop |

*Note: The theme uses a custom `md` breakpoint at 853px instead of the standard 768px.

## Component Specifications

### Day Selector (`layouts/partials/day-selector.html`)

| Property | Mobile | Tablet (md:) | Desktop |
|----------|--------|--------------|---------|
| Layout | Horizontal scroll | Centered flex | Centered flex |
| Gap | 1.5 units | 3 units | 3 units |
| Button min-height | 44px | 44px | 44px |
| Button padding | px-3 py-2.5 | px-5 py-3 | px-5 py-3 |
| Text size | text-xs | text-base | text-base |

Key features:
- `overflow-x-auto` enables horizontal scrolling on mobile
- `md:justify-center` centers tabs on larger screens
- `min-h-[44px]` ensures touch target compliance
- Hidden scrollbar with `.scrollbar-hide` class

### Event Card (`layouts/partials/event-card.html`)

| Property | Mobile | Tablet/Desktop |
|----------|--------|----------------|
| Content padding | p-3 | p-4 |
| Title text | text-base | text-lg |
| Metadata text | text-xs | text-sm |
| Icon size | h-3.5 w-3.5 | h-4 w-4 |
| Card max-width | max-w-sm | none |

Key features:
- Responsive padding scales with viewport
- Title and metadata text scale appropriately
- Icons scale proportionally
- Card width constrained on mobile for centering in single-column

### Event Grid (`layouts/partials/home/custom.html`)

| Property | Mobile | Tablet (sm:) | Desktop (lg:) |
|----------|--------|--------------|---------------|
| Columns | 1 | 2 | 3 |
| Gap | gap-4 | gap-5 | gap-6 |
| Horizontal padding | px-4 | px-6 | px-0 |

Key features:
- Grid automatically adjusts columns: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`
- Gap increases progressively for visual breathing room
- Edge padding on mobile/tablet, removed on desktop

### Event Detail Page (`layouts/events/single.html`)

| Property | Mobile | Tablet | Desktop |
|----------|--------|--------|---------|
| Hero aspect ratio | 16:9 | 21:9 | 21:9 |
| Title size | text-2xl | text-3xl | text-4xl |
| Container padding | px-4 | px-6 | px-0 |
| CTA button | Full width | Auto width | Auto width |

Key features:
- Responsive hero image aspect ratio: `aspect-[16/9] sm:aspect-[21/9]`
- Title scales across three breakpoints
- Hero image bleeds to edge on mobile (`-mx-4`)
- Full-width CTA button on mobile for better touch target

## Touch Target Compliance

All interactive elements meet the minimum 44x44px touch target requirement:

- Day selector buttons: `min-h-[44px]`
- Navigation links: `min-h-[44px] py-2`
- Category badges: `min-h-[36px] sm:min-h-[40px]`
- CTA buttons: `min-h-[48px]`

## Viewport Test Matrix

| Component | Mobile (<640px) | Tablet (640-1024px) | Desktop (>1024px) |
|-----------|-----------------|---------------------|-------------------|
| Day selector | Horizontal scroll | Centered | Centered |
| Event grid | 1 column | 2 columns | 3 columns |
| Card image | 16:9 | 16:9 | 16:9 |
| Detail hero | 16:9 | 21:9 | 21:9 |
| CTA button | Full width | Auto width | Auto width |

## Accessibility Considerations

- No horizontal page scroll at any viewport
- All text remains readable without zooming
- Touch targets meet 44x44px minimum
- ARIA labels and roles properly implemented
- Focus states visible on all interactive elements
