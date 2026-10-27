"""Info View text for every control: what Live shows at the bottom left when the control is hovered (the
'annotation' of a live.* object; lib/m4l.py's Patch.patcher adds it by the control's long name, for the
device named in its logo). One line each, in the manuals' words. (Written by the Dye House's export: the Utilities' texts.)
"""


DEVICE_INFO = {}

ANNOTATIONS = {'Tannin': {'Root': "The key's root, for every family device on Tannin key",
            'Scale': "The key's scale, microtonal ones included, for every device on Tannin key",
            'From Live': "Copies Live's current scale into Root and Scale, once, when pressed"},
 'Dye Lot': {'Set': 'Sends the key heard to Tannin, which sets the key of every device following it',
             'Auto': 'Sends it every bar by itself: the house follows whatever you play',
             'Memory': 'How long a note keeps counting: its weight halves every 1, 2, 4 or 8 bars'},
 'Warp': {'Cable': "The cable (A-D) this track's notes and per-note expression go out on",
          'Thru': 'Also lets the notes through to the instrument on this track'},
 'Weft': {'Cable': "The cable (A-D) to receive: another track's notes and per-note expression"},
 'Selvedge': {'Root': "The scale's root the tuner measures against",
              'Scale': 'The scale the tuner measures against, microtonal ones included',
              'Key': "Which key it plays: Own (its Root and Scale), Live (the playing clip's scale, else Live's) "
                     "or Tannin (the family's key). Never changes Root or Scale"}}

SHOWN = {'Tannin': {'_device': 'Tannin: one key for the whole set. Set its Root and Scale, and every family device on '
                       'Tannin key plays in it.'},
 'Dye Lot': {'_device': 'Dye Lot: hears the key you play in, and sends it to Tannin with SET (or every bar, with '
                        'AUTO).'},
 'Warp': {'_device': "Warp: sends this track's notes and per-note expression down a cable, A to D, for Weft or a "
                     'family device to play.'},
 'Weft': {'_device': 'Weft: plays the notes that arrive on a cable, A to D, from Warp on another track.'},
 'Selvedge': {'_device': "Selvedge: a tuner for the family's scales. It shows the note you play and how far it is "
                         "from the scale's step."}}

SHOWN_PATTERNS = [('-dicea?(-js)?$',
  "DICE: rolls this card's controls to new values. The arrows beside it go back and forth through the rolls."),
 ('-undoa?(-js)?$', "Back to the roll before (this card's dice)."),
 ('-redoa?(-js)?$', "Forward to the next roll again (this card's dice).")]
