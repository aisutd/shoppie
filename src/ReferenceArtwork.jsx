import { useId } from 'react'

// these display masks hide the surroundings while keeping the source photos intact
const photoFrames = {
  'neo-silver.jpg': [500, 667, '20 66 464 486',
    'M119 322 L128 92 Q129 73 146 74 L455 73 Q477 73 474 91 L454 322 L462 522 Q462 544 441 544 L41 466 Q18 462 27 448 Z'],
  'neo-indigo-front.jpg': [500, 667, '22 64 479 500',
    'M29 93 Q23 71 46 72 L364 73 Q384 73 382 96 L371 296 L491 449 Q501 465 484 472 L96 556 Q77 559 75 542 L65 348 Q64 337 70 330 L57 321 Z'],
  'air-m5.jpg': [500, 500, '19 7 461 483',
    'M153 35 Q153 24 165 25 L457 16 Q473 14 472 28 L444 251 Q443 258 438 261 Q445 264 444 275 L432 461 Q431 483 412 486 L39 397 Q24 394 27 381 L133 234 Q137 228 148 230 Z'],
  'pro-m5.jpg': [330, 247, '53 0 217 245',
    'M95 9 Q97 2 107 3 L257 11 Q266 11 263 21 L250 120 Q249 128 240 129 L250 225 Q250 239 239 241 L67 219 Q56 217 61 206 L94 123 Z'],
  'airpods-4.jpg': [500, 512, '0 5 500 497',
    'M7 224 C5 196 23 168 66 139 L184 47 C212 24 235 14 260 14 C304 14 334 46 334 101 C344 107 353 119 365 126 C377 113 395 114 407 126 C420 141 428 161 439 183 L478 247 C493 273 497 303 483 332 C463 370 421 400 382 431 L304 484 C284 498 259 503 233 497 C206 491 180 476 164 459 L103 380 C94 368 92 351 100 337 L109 320 L105 304 C76 307 50 302 29 281 C15 268 7 248 7 224 Z'],
  'sony-xm6-black.jpg': [640, 960, '225 374 412 455',
    'M239 574 C244 481 306 406 405 385 C490 368 538 412 567 493 L576 527 C603 538 623 555 627 582 C635 611 616 660 599 698 C587 728 550 749 517 742 C489 735 476 714 473 690 C469 658 480 607 497 574 C510 551 528 539 549 531 C537 473 491 430 453 427 C382 414 302 464 275 548 C265 579 264 605 271 627 L298 639 C324 626 373 642 419 664 C450 679 464 701 465 727 C469 761 442 806 407 815 C372 824 321 799 289 780 C250 759 231 733 237 703 C241 675 257 652 253 641 C240 625 235 599 239 574 Z'],
  'sony-xm6-silver.jpg': [640, 960, '47 338 495 316',
    'M57 521 C57 486 81 454 122 444 L135 430 C181 380 245 364 304 367 C367 368 406 399 411 437 C415 478 397 513 379 539 L358 555 C351 604 318 633 274 642 C221 652 169 638 145 611 C111 632 74 606 63 566 C57 550 56 535 57 521 Z M144 452 C169 465 177 484 180 508 C222 480 275 476 313 486 C330 490 343 504 346 516 C361 492 379 466 376 443 C372 420 344 411 302 410 C239 410 189 429 144 452 Z'],
}

const categoryPaths = {
  laptops: 'M15 45V17a4 4 0 0 1 4-4h34a4 4 0 0 1 4 4v28M15 45h42l8 9a3 3 0 0 1-3 4H10a3 3 0 0 1-3-4l8-9Zm16 6h10',
  monitors: 'M14 13h44a5 5 0 0 1 5 5v27a5 5 0 0 1-5 5H14a5 5 0 0 1-5-5V18a5 5 0 0 1 5-5Zm22 37v9m-12 0h24',
  tablets: 'M22 9h28a5 5 0 0 1 5 5v44a5 5 0 0 1-5 5H22a5 5 0 0 1-5-5V14a5 5 0 0 1 5-5Zm11 47h6',
  headphones: 'M13 39v-6a23 23 0 0 1 46 0v6M13 37h7a4 4 0 0 1 4 4v13a4 4 0 0 1-4 4h-5a6 6 0 0 1-6-6v-9a6 6 0 0 1 4-6Zm46 0h-7a4 4 0 0 0-4 4v13a4 4 0 0 0 4 4h5a6 6 0 0 0 6-6v-9a6 6 0 0 0-4-6Z',
  storage: 'M11 24h48a5 5 0 0 1 5 5v14a5 5 0 0 1-5 5H11a3 3 0 0 1-3-3V27a3 3 0 0 1 3-3Zm9 7h10v10H20zm18 0h10v10H38zm18 0v10',
}

function ReferenceArtwork({ product, hasImage, onError }) {
  const maskId = useId()
  const frame = photoFrames[product.image_url?.split('/').pop()]
  if (hasImage && frame) {
    const [width, height, viewBox, outline] = frame
    return (
      <svg viewBox={viewBox} role="img" aria-label={product.title} className="h-full w-full p-4 drop-shadow-sm">
        <defs><clipPath id={maskId}><path d={outline} clipRule="evenodd" /></clipPath></defs>
        <image href={product.image_url} width={width} height={height} clipPath={`url(#${maskId})`} onError={onError} />
      </svg>
    )
  }
  if (hasImage) {
    return <img src={product.image_url} alt={product.title} className="h-full w-full object-contain p-3" onError={onError} />
  }
  return (
    <div className="grid justify-items-center gap-2 text-slate-500">
      <svg aria-hidden="true" viewBox="0 0 72 72" className="size-16 rounded-2xl bg-slate-200/80 p-2 sm:size-20">
        <path d={categoryPaths[product.category] || categoryPaths.storage}
          fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="text-xs font-medium">Category illustration</span>
    </div>
  )
}

export default ReferenceArtwork
