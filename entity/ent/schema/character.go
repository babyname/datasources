package schema

import (
	"entgo.io/ent"
	"entgo.io/ent/dialect/entsql"
	"entgo.io/ent/schema"
	"entgo.io/ent/schema/field"
)

// Character is the data-source view of a Chinese character.
//
// Field set mirrors the consumer contract in fate's resources/character.json
// (20 flat fields), NOT fate's internal ent schema (which adds edges and EE
// fields). Any export from this schema must pass fate's verify_dataset.py.
//
// Required vs optional follows the observed character.json distribution:
// 30060 records; kangxi_stroke/pinyin and the boolean flags are sparse, while
// char/unicode/wu_xing/radical_stroke/simplified_stroke/traditional_stroke/
// science_stroke/source are present on every record.
type Character struct {
	ent.Schema
}

func (Character) Fields() []ent.Field {
	return []ent.Field{
		field.String("char").NotEmpty().Unique(), // 汉字本身
		field.String("unicode"),                  // U+XXXX 码点
		field.Bool("is_simplified"),
		field.Bool("is_traditional"),
		field.Bool("is_kangxi"),
		field.Bool("is_variant"),
		field.Strings("pinyin"), // 多音字列表
		field.String("radical"), // 部首
		field.Int("radical_stroke").NonNegative(),
		field.Int("simplified_stroke").NonNegative(),
		field.Int("traditional_stroke").NonNegative(),
		field.Int("kangxi_stroke").NonNegative(),
		field.Int("science_stroke").NonNegative(),
		field.String("wu_xing"), // 五行：木/火/水/金/土
		field.Bool("regular"),
		field.Bool("nameable"),
		field.String("meaning"),
		field.String("source"), // 溯源标识，如 unihan/kangxi/v4_dbfix
		field.String("simplified_of_char"),
		field.String("variant_of_char"),
	}
}

func (Character) Edges() []ent.Edge {
	return nil
}

func (Character) Annotations() []schema.Annotation {
	return []schema.Annotation{
		entsql.Annotation{Table: "character"},
	}
}
