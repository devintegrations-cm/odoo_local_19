from odoo import models, fields

class FaceDetails(models.Model):
    _name = 'face.details'
    _description = 'Face Details'

    pos_order_uid = fields.Char("Order Number")

    # Existing fields
    bounding_box_width = fields.Float(string="Bounding Box Width")
    bounding_box_height = fields.Float(string="Bounding Box Height")
    bounding_box_left = fields.Float(string="Bounding Box Left")
    bounding_box_top = fields.Float(string="Bounding Box Top")

    age_range_low = fields.Integer(string="Age Range Low")
    age_range_high = fields.Integer(string="Age Range High")

    smile_value = fields.Boolean(string="Smile Value")
    smile_confidence = fields.Float(string="Smile Confidence")

    eyeglasses_value = fields.Boolean(string="Eyeglasses Value")
    eyeglasses_confidence = fields.Float(string="Eyeglasses Confidence")

    sunglasses_value = fields.Boolean(string="Sunglasses Value")
    sunglasses_confidence = fields.Float(string="Sunglasses Confidence")

    gender_value = fields.Selection([
        ('Male', 'Male'),
        ('Female', 'Female')
    ], string="Gender Value")
    gender_confidence = fields.Float(string="Gender Confidence")

    beard_value = fields.Boolean(string="Beard Value")
    beard_confidence = fields.Float(string="Beard Confidence")

    mustache_value = fields.Boolean(string="Mustache Value")
    mustache_confidence = fields.Float(string="Mustache Confidence")

    eyes_open_value = fields.Boolean(string="Eyes Open Value")
    eyes_open_confidence = fields.Float(string="Eyes Open Confidence")

    mouth_open_value = fields.Boolean(string="Mouth Open Value")
    mouth_open_confidence = fields.Float(string="Mouth Open Confidence")

    # Emotion fields with prefix 'emotions_'
    emotions_happy_value = fields.Boolean(string="Happy")
    emotions_happy_confidence = fields.Float(string="Happy Confidence")

    emotions_sad_value = fields.Boolean(string="Sad")
    emotions_sad_confidence = fields.Float(string="Sad Confidence")

    emotions_angry_value = fields.Boolean(string="Angry")
    emotions_angry_confidence = fields.Float(string="Angry Confidence")

    emotions_confused_value = fields.Boolean(string="Confused")
    emotions_confused_confidence = fields.Float(string="Confused Confidence")

    emotions_disgusted_value = fields.Boolean(string="Disgusted")
    emotions_disgusted_confidence = fields.Float(string="Disgusted Confidence")

    emotions_surprised_value = fields.Boolean(string="Surprised")
    emotions_surprised_confidence = fields.Float(string="Surprised Confidence")

    emotions_calm_value = fields.Boolean(string="Calm")
    emotions_calm_confidence = fields.Float(string="Calm Confidence")

    emotions_unknown_value = fields.Boolean(string="Unknown")
    emotions_unknown_confidence = fields.Float(string="Unknown Confidence")

    emotions_fear_value = fields.Boolean(string="Fear")
    emotions_fear_confidence = fields.Float(string="Fear Confidence")

    # Landmarks fields
    landmark_x = fields.Float(string="Landmark X Coordinate", required=False)
    landmark_y = fields.Float(string="Landmark Y Coordinate", required=False)

    pose_roll = fields.Float(string="Pose Roll")
    pose_yaw = fields.Float(string="Pose Yaw")
    pose_pitch = fields.Float(string="Pose Pitch")

    quality_brightness = fields.Float(string="Quality Brightness")
    quality_sharpness = fields.Float(string="Quality Sharpness")

    confidence = fields.Float(string="Confidence")

    face_occluded_value = fields.Boolean(string="Face Occluded Value")
    face_occluded_confidence = fields.Float(string="Face Occluded Confidence")

    eye_direction_yaw = fields.Float(string="Eye Direction Yaw")
    eye_direction_pitch = fields.Float(string="Eye Direction Pitch")
    eye_direction_confidence = fields.Float(string="Eye Direction Confidence")

    orientation_correction = fields.Selection([
        ('ROTATE_0', 'Rotate 0'),
        ('ROTATE_90', 'Rotate 90'),
        ('ROTATE_180', 'Rotate 180'),
        ('ROTATE_270', 'Rotate 270')
    ], string="Orientation Correction")
