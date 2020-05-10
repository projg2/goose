from django.db import models


class DataClass(models.Model):
    """
    Class of statistical data stored in the database

    A single class of data reported by the client.  `name` indicates
    the key in JSON report that contains the data, and `data_type`
    indicates the expected contents type.  If `public` is True,
    the data is included in output JSON, otherwise it is only kept
    for internal use.
    """

    class DataClassType(models.IntegerChoices):
        """
        Data type for `DataClass`

        The type of data submitted as `DataClass`.

        `STRING` means that the report contains a single string value.
        The count for the value is increased.

        `STRING_ARRAY` means that the report contains an array of string
        values.  The counts for all the values listed are increased.
        """

        STRING = 1
        STRING_ARRAY = 2

    name = models.CharField(
        help_text='Name used in submission JSON',
        max_length=32,
        unique=True)
    description = models.CharField(
        help_text='Human-readable description of the data',
        max_length=128)
    data_type = models.IntegerField(
        choices=DataClassType.choices,
        help_text='Type of data reported')
    public = models.BooleanField(
        help_text='Whether the data is a publicly reported statistic')

    def __str__(self) -> str:
        return f'data class: {self.name}'


class Value(models.Model):
    """
    Known value for given `DataClass`

    A single (unique) value that was submitted at least once.  This
    model is used as a dictionary to avoid repeating the same strings.

    `data_class` specifies the relevant data class.
    `value` is the value.
    """

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name='unique_value',
                fields=['data_class', 'value']),
        ]

    data_class = models.ForeignKey(
        'DataClass',
        help_text='Class of the data represented by the value',
        on_delete=models.CASCADE)
    value = models.CharField(
        help_text='The value',
        max_length=256)

    def __str__(self) -> str:
        return f'value: {self.value}; of {self.data_class}'


class Count(models.Model):
    """
    Partial count towards the statistic

    A partial count of a single value occurrences.

    `value` is the value.  It implies the data type as well.
    `count` is the number of occurrences in the partial sum.

    `inclusion_time` specifies the timestamp for including the data
    in public statistics.  It is initially null, preventing the data
    from being included until the next bulk update.  Afterwards,
    it is used to remove outdated data.
    """

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name='unique_count',
                fields=['value', 'inclusion_time']),
        ]

    value = models.ForeignKey(
        'Value',
        help_text='The value',
        on_delete=models.CASCADE)
    count = models.IntegerField(
        default=1,
        help_text='Number of occurrences of the value')
    inclusion_time = models.DateTimeField(
        default=None,
        help_text='Timestamp of including the data in overall statistic',
        null=True)

    def __str__(self) -> str:
        return (f'count: {self.count} of {self.value}, included: '
                f'{self.inclusion_time}')
