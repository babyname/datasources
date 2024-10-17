package schema

import (
	"entgo.io/ent"
	"entgo.io/ent/dialect/entsql"
	"entgo.io/ent/schema"
	"entgo.io/ent/schema/field"
)

type Character struct {
	ent.Schema
}

func (Character) Fields() []ent.Field {
	return []ent.Field{
		field.Strings("pin_yin"),           // 拼音
		field.String("ch"),                 // 汉字
		field.Int("stroke"),                // 笔画
		field.String("radical"),            // 偏旁
		field.Int("radical_stroke"),        // 偏旁笔画
		field.Bool("is_kang_xi"),           // 是否是康熙字
		field.Int("kang_xi_stroke"),        // 康熙字笔画
		field.Bool("is_simple"),            // 是否是简体字
		field.Int("simple_stroke"),         // 简体笔画
		field.Bool("is_traditional"),       // 是否是传统字
		field.Int("traditional_stroke"),    // 传统笔画
		field.Bool("is_regular"),           // 是否是常用字
		field.Int("science_stroke"),        // 科学笔画
		field.Bool("is_science"),           // 是否是科学字
		field.String("wuxing"),             // 五行
		field.String("luck"),               // 吉凶
		field.Strings("variant_character"), // 变体字符
		field.Text("comment"),              // 注释
		//field.String("id").StorageKey("hash"), // id
		//field.String("simple_radical"),          // 简体偏旁
		//field.Int("simple_radical_stroke"),      // 简体偏旁笔画
		//field.String("traditional_radical"),     // 传统偏旁
		//field.Int("traditional_radical_stroke"), // 传统偏旁笔画
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
