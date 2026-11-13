-- Documentation only: seven rows verified by SELECT and exported in full.
-- No permanent deletion is approved. Do not replace ROLLBACK without approval.
-- Run only in an authorized administrative SQL session; do not expand app grants.
BEGIN;

WITH reviewed_ids(id) AS (
    VALUES
      ('09aad996-a857-40f2-b3eb-d107ad17c167'::uuid), -- Just Funky ceramic mug
      ('77ff438a-aaf9-4231-9972-72d67030b0b4'::uuid), -- Shopkins toy
      ('9f5d94f2-2bb2-4320-ba87-80732a4ac113'::uuid), -- Silver Buffalo ceramic mug
      ('a03b06f1-b72e-4769-8a96-3c6f080bc9db'::uuid), -- Thyme & Table ceramic mug
      ('a223e5ae-6633-4e84-aa5c-d8835511597f'::uuid), -- Marvel ceramic mug
      ('a3d93411-fa19-4510-99fe-78a79b7fedd0'::uuid), -- Peanuts ceramic mug
      ('a555dd21-adb8-42bb-84a5-3cae63d8c782'::uuid)  -- Yellowstone ceramic mug
)
DELETE FROM public.products AS p
USING reviewed_ids AS r
WHERE p.id = r.id
  AND p.title ~* '\m(ceramic.*mug|shopkins)\M'
RETURNING p.*;

ROLLBACK;
